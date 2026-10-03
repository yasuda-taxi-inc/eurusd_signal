# EUR/USD シグナル通知（Twelve Data + GitHub Actions）

リポジトリ直下の `signals.csv` に書いたシナリオを5分足の確定ごとに判定し、成立したら ntfy / Discord / Telegram / LINE に通知します。
（USD/JPY用の別リポジトリと同じ構成。EUR/USD は 1pip=0.0001、価格は5桁表示）

## セットアップ
1. **publicリポジトリ**を作ってこのフォルダの中身を push（privateはActions無料枠が不足しがち）
   - リポジトリ直下に `.github/workflows/signal-scan.yml`・`scanner/`・`signals.csv`・`state/` が来るように（フォルダごと入れ子にしない）
2. Settings → Secrets and variables → Actions → Secrets: `TWELVE_DATA_API_KEY`、通知先（`NTFY_TOPIC` など）
3. Actions → `eurusd-signal-scan` → Run workflow →「テスト通知」にチェックで通知経路を確認
4. `signals.csv` にシナリオを書いて commit（ヘッダのみの間は何もせずスキップ。APIも消費しません）

## 毎日の使い方
CSVを差し替えて commit するだけ。**CSVを最後にコミットした時刻以降の足だけ**で判定します（前日の値動きで誤発報しない）。
手動で開始時刻を指定したい場合は Variables に `SIGNAL_SINCE`（例 `2026-10-05T09:00:00+09:00`）。

## Twelve Data 無料枠（800回/日）
EUR/USD単体で 288回/日（5分ごと・日〜金）。USD/JPYの別リポジトリと**同じAPIキー**を使うと合算で消費されます（288+288=576回/日）。
時間帯を絞る場合は workflow の cron（UTC）を調整（日本時間 = UTC+9）。

## 手元での確認
```
python3 -m scanner.main --check                                   # CSVの解釈結果を表示（最初に必ず確認）
python3 -m unittest
python3 -m scanner.main --bars-csv bars.csv   # 過去5分足CSV(datetime,open,high,low,close)でリプレイ
TWELVE_DATA_API_KEY=xxx python3 -m scanner.main --dry-run              # 取得→判定のみ（通知なし）
```

## 調整用の環境変数（任意・pips指定）
`PAIR`(EURUSD) 使う通貨ペア（workflow で指定済み）/ `TOL_PIPS`(3) 「前後」の許容幅 / `MAX_ENTRY_DEVIATION_PIPS`(8) 成立時の終値とエントリー目安の最大乖離 / `COOLDOWN_BARS`(12) / `NOTIFY_MAX_AGE_MIN`(30)
※ EUR/USD は値動きが小さいので、実運用前にCSVに合わせて見直してください。

## 対応している条件の言い回し
`M5|M15で◯◯割れ|超え` / `◯◯回復` / `A～Bへの戻り` / `A～Bへの戻り失敗` / `A～Bを支持化|抵抗化` / `◯◯前後で安値更新に失敗` / `押しを維持` / `反落確認|反発確認` / 末尾に `◯◯付近で売り|買い`。
未対応の文はエラーにします（`--check` で確認）。

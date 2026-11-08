# Mem0 LOCOMO Single-Hop Experiment

This repository contains the open-source Mem0: https://github.com/mem0ai/mem0 . Python SDK and a small-scale reproduction of the single-hop question-answering evaluation in the Mem0 paper: https://arxiv.org/abs/2504.19413v1 .

The experiment uses the full conversation at index 0 in LOCOMO-10 and its 70 category-4 questions. It compares a baseline semantic threshold of **0.1** with **0.5** while retaining Top-30 memories per speaker and using the same local Qdrant memory store. The threshold run generates and judges its own answers. Each answer is judged 10 times. 
**Note**: The baseline experiment （threshold = 0.1） must be run prior to the threshold = 0.5 comparison experiment.

The experiment is a subset using the local open-source SDK, not an exact reproduction of the paper's hosted full benchmark. 

## Requirements

- macOS or Linux, Git, and Python 3.10 with `venv` and `pip` (the measured run used Python 3.10.22).
- Internet access to install dependencies and call the model provider. A first `tiktoken` run may also download its tokenizer data.
- A Zhizengzeng or official OpenAI API key with access to `gpt-4o-mini` and `text-embedding-3-small`. No hosted Mem0 account or local GPU is needed.
- The experiment scripts and paper-era prompt files in this branch. Download the dataset and NLTK data as described below; neither is included in the repository.


## 1. Clone and install

```bash
git clone --branch feature/locomo-threshold-experiment https://github.com/aaayolo/mem0.git
cd mem0

python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r locomo-experiment/requirements.txt
```

Run all remaining commands from the repository root with this environment active. The requirements file installs the local repository in editable mode, along with versions of the main experiment dependencies used in the measured run. 

Download the public dataset and English NLTK tokenizer data:

```bash
curl -fL https://raw.githubusercontent.com/snap-research/locomo/3eb6f2c585f5e1699204e3c3bdf7adc5c28cb376/data/locomo10.json -o locomo-experiment/locomo10.json
python -c 'import hashlib; from pathlib import Path; p = Path("locomo-experiment/locomo10.json"); h = hashlib.sha256(p.read_bytes()).hexdigest(); print("SHA-256:", h); assert h == "79fa87e90f04081343b8c8debecb80a9a6842b76a7aa537dc9fdf651ea698ff4", "Unexpected dataset; do not run the experiment"'
curl -fL https://raw.githubusercontent.com/nltk/nltk_data/550b6625bcef1f2abff2ff770a5a0d272c9c6b2a/packages/tokenizers/punkt_tab.zip -o locomo-experiment/punkt_tab.zip
python -c 'import hashlib; from pathlib import Path; p = Path("locomo-experiment/punkt_tab.zip"); h = hashlib.sha256(p.read_bytes()).hexdigest(); print("SHA-256:", h); assert h == "e57f64187974277726a3417ca6f181ec5403676c717672eef6a748a7b20e0106", "Unexpected tokenizer archive; do not extract"'
python -c 'from pathlib import Path; from zipfile import ZipFile; root = Path("locomo-experiment/nltk_data/tokenizers"); names = ("collocations.tab", "sent_starters.txt", "abbrev_types.txt", "ortho_context.tab"); dest = root / "punkt_tab/english"; dest.mkdir(parents=True, exist_ok=True); z = ZipFile("locomo-experiment/punkt_tab.zip"); [(dest / name).write_bytes(z.read("punkt_tab/english/" + name)) for name in names]; z.close(); print("English tokenizer installed")'
```

Confirm the SDK imports from this checkout:

```bash
python -c 'import mem0; print(mem0.__file__)'
python locomo-experiment/locomo_pilot.py --help
python locomo-experiment/locomo_threshold_ablation.py --help
```

These commands do not call the model API. The threshold script may access the internet to obtain `tiktoken` encoding data on first use.

## 2. Configure credentials and budget

Create a private file containing **only** the API key, then edit it locally:

```bash
touch .venv/zhizengzeng.key
chmod 600 .venv/zhizengzeng.key
```

To use the official OpenAI API instead, create a **separate** key file and add the official key to it:

```bash
touch .venv/openai.key
chmod 600 .venv/openai.key
```

Select it with `--provider openai`. The default remains `--provider zhizengzeng`. OpenAI runs use `locomo-experiment/locomo-pilot-conv0-openai/`, a separate memory store and results directory. First run the OpenAI baseline; its threshold run reuses that OpenAI baseline, not the Zhizengzeng store.
**Note**: If OpenAI API calls fail, it is recommended to use the zhizengzeng interface. The web link for zhizengzeng is [https://platform.zhizengzeng.com/#/home](https://platform.zhizengzeng.com/#/home).


## 3. Start a fresh baseline

The scripts resume from `locomo-experiment/locomo-pilot-conv0/` if it already exists. To perform a **new independent run**, first move the entire existing directory to a safe backup location, including `qdrant/`, `history.db`:

```bash
# Default: Zhizengzeng
if [ -e locomo-experiment/locomo-pilot-conv0 ]; then
  if [ -e locomo-experiment/locomo-pilot-conv0-backup ]; then
    echo "Backup path already exists; choose another backup location before proceeding."
  else
    mv locomo-experiment/locomo-pilot-conv0 locomo-experiment/locomo-pilot-conv0-backup
  fi
fi

# Optional: OpenAI
if [ -e locomo-experiment/locomo-pilot-conv0-openai ]; then
  if [ -e locomo-experiment/locomo-pilot-conv0-openai-backup ]; then
    echo "Backup path already exists; choose another backup location before proceeding."
  else
    mv locomo-experiment/locomo-pilot-conv0-openai locomo-experiment/locomo-pilot-conv0-openai-backup
  fi
fi
```

If the backup already exists, stop and choose another name before running the baseline. 
Then evaluates all 70 questions:

```bash
# Default: Zhizengzeng
python -u locomo-experiment/locomo_pilot.py --sample-size 70 --seed 42 --judge-runs 10

# Optional: OpenAI
python -u locomo-experiment/locomo_pilot.py --provider openai --sample-size 70 --seed 42 --judge-runs 10
```

The default sample size is 20, so the explicit `--sample-size 70` is required. The baseline may take considerable time and makes paid API calls (About 5 CNY in Zhizengzeng). Keep the saved memory store and baseline state together, the threshold run requires both.

## 4. Run the threshold 0.5 comparison

After the baseline has completed all 70 questions and 10 judgments per answer, run:

```bash
# Default: Zhizengzeng
python -u locomo-experiment/locomo_threshold_ablation.py --experiment threshold05

# Optional: OpenAI
python -u locomo-experiment/locomo_threshold_ablation.py --provider openai --experiment threshold05
```

The script validates the dataset and baseline, reuses the same Qdrant store, and saves the modified run separately. It resumes existing threshold results; it does not automatically repeat completed questions. Do not run the baseline and threshold processes simultaneously against the same local Qdrant store.

## 5. Inspect results

| Path | Contents |
|---|---|
| `locomo-experiment/locomo-pilot-conv0/state.json` | Baseline ingestion progress and per-question results |
| `locomo-experiment/locomo-pilot-conv0/summary-70-seed-42.json` | Baseline metric summary |
| `locomo-experiment/locomo-pilot-conv0/threshold05-ablation/state.json` | Threshold run's per-question results and usage |
| `locomo-experiment/locomo-pilot-conv0/threshold05-ablation/summary.json` | Baseline-versus-threshold comparison |
| `locomo-experiment/locomo-pilot-conv0/qdrant/` | Shared local vector memory |
| `locomo-experiment/locomo-pilot-conv0/history.db` | Local Mem0 history |

View a summary without making API calls:

```bash
python -m json.tool locomo-experiment/locomo-pilot-conv0/threshold05-ablation/summary.json
```

Both groups' answer token counts are reconstructed with the same tokenizer and estimated chat framing, rather than billed usage. API-reported usage for the threshold run is also retained separately. Cost figures in the summaries are estimates, not provider invoices. The reported F1, BLEU-1, and LLM-judge scores cover just one conversation, so they are not directly comparable to the full paper benchmark.

## Resume and troubleshooting

- **Interrupted run:** rerun the same command to resume completed work. If the baseline reports an uncertain in-flight ingestion, inspect the state and memory store before deciding how to recover; blindly repeating a write can duplicate or alter memories.
- **Missing baseline or memory store:** run the complete baseline first. A copied state file alone is insufficient. The repository's Git rules ignore `*.db`, including `history.db`; cloning does not guarantee a complete saved memory store.
- **Existing completed results:** rerunning a completed command normally resumes/skips completed work rather than creating an independent trial. Back up the entire run directory and start fresh for a new trial.
- **Missing key or unauthorized API:** check the private key file, provider account balance, model access, and endpoint. Do not post the key in an issue or log.
- **Missing tokenizer data or prompts:** repeat the tokenizer installation in step 1 and verify that the cloned branch includes the three paper-era prompt files under `locomo-experiment/paper-2025/`.
- **Other Mem0 features:** this README covers the LOCOMO experiment. For the broader project, see the official documentation: https://docs.mem0.ai.

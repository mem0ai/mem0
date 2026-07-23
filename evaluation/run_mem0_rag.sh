#!/usr/bin/bash
#SBATCH -J mem0-evals
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-gpu=8
#SBATCH --mem-per-gpu=32G
#SBATCH -p batch_ce_ugrad
#SBATCH -t 1-0
#SBATCH -o /data/delta9043/repos/mem0/evaluation/logs/slurm-%A.out

# 데이터셋 및 결과 파일 로컬 복사
mkdir -p /local_datasets/mem0
cp /data/delta9043/repos/mem0/evaluation/dataset/locomo10.json /local_datasets/mem0/
cp /data/delta9043/repos/mem0/evaluation/dataset/locomo10_rag.json /local_datasets/mem0/
cp /data/delta9043/repos/mem0/evaluation/results/rag_results_1000_k1.json /local_datasets/mem0/

cd /data/delta9043/repos/mem0/evaluation
source /data/delta9043/anaconda3/etc/profile.d/conda.sh
conda activate mem0

# NLTK 데이터 다운로드
python -c "import nltk; nltk.download('punkt_tab'); nltk.download('wordnet')"

python evals.py \
  --input_file /local_datasets/mem0/rag_results_1000_k1.json \
  --output_file /data/delta9043/repos/mem0/evaluation/results/rag_eval_metrics.json

exit 0

exit 0
#!/usr/bin/bash
#SBATCH -J mem0-search
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-gpu=8
#SBATCH --mem-per-gpu=32G
#SBATCH -p batch_ce_ugrad
#SBATCH -t 0-6
#SBATCH -o /data/delta9043/repos/mem0/evaluation/logs/slurm-%A.out

mkdir -p /local_datasets/mem0
cp /data/delta9043/repos/mem0/evaluation/dataset/locomo10.json /local_datasets/mem0/
cp /data/delta9043/repos/mem0/evaluation/dataset/locomo10_rag.json /local_datasets/mem0/

cd /data/delta9043/repos/mem0/evaluation

source /data/delta9043/anaconda3/etc/profile.d/conda.sh
conda activate mem0

export NLTK_DATA=/data/delta9043/nltk_data

python run_experiments.py \
  --technique_type mem0 \
  --method search \
  --top_k 30

exit 0

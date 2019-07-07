#!/bin/bash

#SBATCH --gres=gpu:1
#SBATCH --mem 16000M
#SBATCH --ntasks 4
#SBATCH --output="./log2.slurm"
#SBATCH --time 48:00:00
#SBATCH -C 'rhel7&pascal'
#SBATCH --mail-user=taylor.archibald@byu.edu   # email address
#SBATCH --mail-type=BEGIN
#SBATCH --mail-type=END
#SBATCH --mail-type=FAIL

#%Module

module purge
module load cuda/10.1
module load cudnn/7.6

group_path="/panfs/pan.fsl.byu.edu/scr/grp/fslg_hwr"
export PATH="${group_path}/env/hwr4_env/bin:$PATH"
which python

cd "${group_path}/taylor_simple_hwr"
python -u train.py --config baseline



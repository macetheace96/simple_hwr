#!/bin/bash

#SBATCH --gres=gpu:1
#SBATCH --mem 16000M
#SBATCH --output="./results/online/log.slurm"
#SBATCH --time 72:00:00
#SBATCH -C 'rhel7'
#SBATCH --mail-user=masonfp@byu.edu   # email address
#SBATCH --mail-type=BEGIN
#SBATCH --mail-type=END
#SBATCH --mail-type=FAIL

#%Module

module purge
module load cuda

export PATH="/fslhome/masonfp/fsl_groups/fslg_hwr/compute/env/hwr_env/bin:$PATH"
which python

cd "/fslhome/masonfp/fsl_groups/fslg_hwr/compute/simple_hwr"
python train.py configs/online_config.json

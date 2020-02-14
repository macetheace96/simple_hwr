import torch
import robust_loss_pytorch
import numpy as np
import torch.nn as nn
from torch import Tensor
from pydtw import dtw
from scipy import spatial
from robust_loss_pytorch import AdaptiveLossFunction
#from sdtw import SoftDTW
import torch.multiprocessing as multiprocessing
from hwr_utils.utils import to_numpy, Counter
from hwr_utils.stroke_recovery import relativefy
from hwr_utils.stroke_dataset import pad, create_gts
from scipy.spatial import KDTree
import time
from loss_module.losses import *
import logging

logger = logging.getLogger("root."+__name__)

class StrokeLoss:
    def __init__(self, parallel=False, vocab_size=4, loss_stats=None, counter=None, device="cuda", **kwargs):
        super(StrokeLoss, self).__init__()
        ### Relative preds and relative GTs:
            # Resample GTs to be relative
            # Return unrelative GTs and Preds
            # This doesn't work that well, because it doesn't learn spaces
        ### Absolute everything
        ### Relative preds from network, then convert to absolute before loss
            # Return unrelative preds

        self.device = device
        self.vocab_size = vocab_size
        self.cosine_similarity = nn.CosineSimilarity(dim=1)
        self.cosine_distance = lambda x, y: 1 - self.cosine_similarity(x, y)
        self.distributions = None
        self.parallel = parallel
        self.counter = Counter() if counter is None else counter
        self.poolcount = max(1, multiprocessing.cpu_count()-8)
        self.poolcount = 2
        self.truncate_preds = True
        self.dtw = None
        self.stats = loss_stats
        self.master_loss_defintion = {} # everything in the master_loss_defition will be evaluated
        self.coefs = []

    def get_loss_fn(self, loss):
        """ Return the right loss function given a loss definition dictionary
            Matching based one loss["name"]

        Args:
            loss:

        Returns:

        """
        # IF THE EXACT SAME LOSS ALREADY EXISTS, DON'T BUILD A NEW ONE
        if loss["name"] in self.master_loss_defintion:
            loss_fn = self.master_loss_defintion[loss["name"]]["fn"]
        elif loss["name"].lower().startswith("l1"):
            loss_fn = L1(**loss, device=self.device).lossfun
        elif loss["name"].lower().startswith("l2"):
            loss_fn = L2(**loss, device=self.device).lossfun
        elif loss["name"].lower().startswith("dtw"):
            loss_fn = DTWLoss(**loss, device=self.device).lossfun
        elif loss["name"].lower().startswith("barron"):
            loss_fn = AdaptiveLossFunction(num_dims=vocab_size, float_dtype=np.float32, device='cpu').lossfun
        elif loss["name"].lower().startswith("ssl"):
            loss_fn = SSL(**loss, device=self.device).lossfun
        elif loss["name"].lower().startswith("cross_entropy"):
            loss_fn = CrossEntropy(**loss, device=self.device).lossfun
        else:
            raise Exception(f"Unknown loss: {loss['name']}")
        return loss_fn

    def build_losses(self, loss_fn_definition):
        """

        Args:
            loss_fn_definition (dict): {name: "",
                                        coef: "",     # multiplied in this module to modify effect on loss used
                                        subcoef: "",  # passed on to loss object
                                        monitor_only: ""}

        Returns:

        """
        if loss_fn_definition is None:
            return

        coefs = []
        master_loss_defintion = {}
        for loss_def in loss_fn_definition:
            loss_fn = self.get_loss_fn(loss_def)
            master_loss_defintion[loss_def["name"]] = {"fn": loss_fn, **loss_def}
            coefs.append(loss_def["coef"])

        self.coefs = Tensor(coefs)
        self.master_loss_defintion = master_loss_defintion

        # Loop through monitor vs effective losses
        for key, item in master_loss_defintion.items():
            logger.info(f"Loss {key}: {item}")

    def main_loss(self, preds, targs, label_lengths, suffix):
        """ Preds: BATCH, TIME, VOCAB SIZE
                    VOCAB: x, y, start stroke, end_of_sequence
        Args:
            preds: Will be in the form [batch, width, alphabet]
            targs: Pass in the whole dictionary, so we can get lengths, etc., whatever we need

            suffix (str): _train or _test
        Returns:

        # Adapatively invert stroke targs if first instance is on the wrong end?? sounds sloooow

        """
        losses = torch.zeros(len(self.master_loss_defintion))
        batch_size = len(preds)
        total_points = tensor_sum(label_lengths)

        ## Loop through loss functions
        for i, loss_name in enumerate(self.master_loss_defintion):
            loss_fn = self.master_loss_defintion[loss_name]["fn"]
            loss_tensor = loss_fn(preds, targs, label_lengths)
            loss = to_value(loss_tensor)
            assert loss > 0

            if not self.master_loss_defintion[loss_name]["monitor_only"]:
                losses[i] = loss_tensor

            # Update loss stat
            self.stats[loss_name + suffix].accumulate(loss)

        if suffix == "_train":
            self.counter.update(training_pred_count=total_points)
            #print(total_points)
        elif suffix == "_test":
            self.counter.update(test_pred_count=total_points)

        combined_loss = torch.sum(losses * self.coefs) # only for the actual gradient loss so that the loss doesn't change with bigger batch sizes;, not the reported one since it will be divided by instances later
        combined_loss_value = to_value(combined_loss)
        return combined_loss, combined_loss_value/batch_size # does the total loss makes most sense at the EXAMPLE level? Don't think 'combined_loss_value' is used anymore

    def barron_loss(self, preds, targs, label_lengths, **kwargs):
        # BATCH, TIME, VOCAB
        vocab_size = preds.shape[-1]
        _preds = preds.reshape(-1, vocab_size)
        _targs = targs.reshape(-1, vocab_size)
        loss = torch.sum(self.barron_loss_fn((_preds - _targs)))
        return loss #, to_value(loss)

if __name__ == "__main__":
    from models.basic import CNN, BidirectionalRNN
    from torch import nn

    vocab_size = 4
    batch = 3
    time = 16
    y = torch.rand(batch, 1, 60, 60)
    targs = torch.rand(batch, time, vocab_size)  # BATCH, TIME, VOCAB
    cnn = CNN(nc=1)
    rnn = BidirectionalRNN(nIn=1024, nHidden=128, nOut=vocab_size, dropout=.5, num_layers=2, rnn_constructor=nn.LSTM)
    cnn_output = cnn(y)
    rnn_output = rnn(cnn_output).permute(1, 0, 2)
    print(rnn_output.shape)  # BATCH, TIME, VOCAB
    loss = StrokeLoss()
    loss = loss.main_loss(None, rnn_output, targs)
    print(loss)


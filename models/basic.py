import torch
from torch import nn
from hwr_utils import *
import os
from torch.autograd import Variable

class MLP(nn.Module):
    def __init__(self, input_size, classifier_output_dimension, hidden_layers, dropout=.5, embedding_idx=None):
        """

        Args:
            input_size (int): Dimension of input
            classifier_output_dimension (int): Dimension of output layer
            hidden_layers (list): A list of hidden layer dimensions
            dropout (float): 0 means no dropout
            embedding_idx: The hidden layer index of the embedding layer starting with 0
                e.g. input-> 16 nodes -> 8 nodes [embedding] -> 16 nodes would be 1
        """

        super().__init__()
        classifier = nn.Sequential()

        def addLayer(i, input, output, use_nonlinearity=True):
            classifier.add_module('drop{}'.format(i), nn.Dropout(dropout))
            classifier.add_module('fc{}'.format(i), nn.Linear(input, output))
            if use_nonlinearity:
                classifier.add_module('relu{}'.format(i), nn.ReLU(True))

        next_in = input_size
        for i, h in enumerate(hidden_layers):
            addLayer(i, next_in, h)
            next_in = h

        # Last Layer - don't use nonlinearity
        addLayer(len(hidden_layers), next_in, classifier_output_dimension, use_nonlinearity=False)
        self.classifier = classifier

        if embedding_idx is None:
            self.embedding_idx = len(classifier) # if no embedding specified, assume embedding=output
        else:
            self.embedding_idx = (embedding_idx + 1) * 3 # +1 for zero index, 3 items per layer

    def forward(self, input, layer="output"):
        input = input.view(input.shape[0], -1)

        if layer == "output":
            output = self.classifier(input) # batch size, everything else
            return output
        elif layer == "output+embedding":
            embedding = self.classifier[0:self.embedding_idx](input)
            output = self.classifier[self.embedding_idx:](embedding)  # batch size, everything else
            return output, embedding
        elif layer == "embedding":
            embedding = self.classifier[0:self.embedding_idx](input)
            return embedding

class BidirectionalRNN(nn.Module):

    def __init__(self, nIn, nHidden, nOut, dropout=.5, num_layers=2, rnn_constructor=nn.LSTM):
        super().__init__()
        print(f"Creating {rnn_constructor.__name__}: in:{nIn} hidden:{nHidden} dropout:{dropout} layers:{num_layers} out:{nOut}")
        self.nIn = nIn
        self.rnn = rnn_constructor(nIn, nHidden, bidirectional=True, dropout=dropout, num_layers=num_layers)
        self.embedding = nn.Linear(nHidden * 2, nOut) # add dropout?

    def forward(self, _input):
        # input [time size, batch size, output dimension], e.g. 404, 8, 1024
        recurrent, _ = self.rnn(_input)
        T, b, h = recurrent.size()
        t_rec = recurrent.view(T * b, h)

        output = self.embedding(t_rec)  # [T * b, nOut]
        output = output.view(T, b, -1)

        return output


class GeneralizedBRNN(nn.Module):

    def __init__(self, nIn, nHidden, nOut, dropout=.5, num_layers=2, rnn_constructor=nn.LSTM, permute=False):
        super().__init__()
        print(
            f"Creating {rnn_constructor.__name__}: in:{nIn} hidden:{nHidden} dropout:{dropout} layers:{num_layers} out:{nOut}")
        self.nIn = nIn
        self.rnn = rnn_constructor(nIn, nHidden, bidirectional=True, dropout=dropout, num_layers=num_layers)
        self.embedding = nn.Linear(nHidden * 2, nOut)  # add dropout?
        self.permute = permute

    def forward(self, _input: torch.tensor):
        # input [time size, batch size, output dimension], e.g. 404, 8, 1024

        if self.permute:
            b, *ch, T = _input.size()
            reshaped_input = _input.permute(3,0,1,2).view(T,b,-1) # put T first, combine CHANNELs and HEIGHT
            recurrent, _ = self.rnn(reshaped_input)
            t_rec = recurrent.view(T * b, -1)
            output = self.embedding(t_rec)  # [T * b, nOut]
            output = output.view(T, b, *ch).permute(1,2,3,0) # change view back, then put T on the end
        else:
            recurrent, _ = self.rnn(_input)
            T, b, h = recurrent.size()
            t_rec = recurrent.view(T * b, h)
            output = self.embedding(t_rec)  # [T * b, nOut]
            output = output.view(T, b, -1)

        return output


class PrintLayer(nn.Module):
    """ Print layer - add to a sequential, e.g.
            nn.Sequential(
            nn.Linear(1, 5),
            PrintLayer(),
    """
    def __init__(self, name=None):
        super().__init__()
        self.name = name

    def forward(self, x):
        # Do your print / debug stuff here
        print(x.size(), self.name)
        return x

class CNN(nn.Module):
    def __init__(self, cnnOutSize=1024, nc=3, leakyRelu=False, type="default"):
        """ Height must be set to be consistent; width is variable, longer images are fed into BLSTM in longer sequences

        The CNN learns some kind of sequential ordering because the maps are fed into the LSTM sequentially.

        Args:
            cnnOutSize: DOES NOT DO ANYTHING! Determined by architecture
            nc:
            leakyRelu:
        """
        super().__init__()
        self.cnnOutSize = cnnOutSize
        #self.average_pool = nn.AdaptiveAvgPool2d((512,2))
        self.pool = nn.MaxPool2d(3, (4, 1), padding=1)
        self.intermediate_pass = 13 if type == "intermediates" else None

        print("Intermediate pass {}".format(self.intermediate_pass))

        if type in ["default", "intermediates"]:
            self.cnn = self.default_CNN(nc=nc, leakyRelu=leakyRelu)
        elif "resnet" in type:
            from models import resnet
            if type=="resnet":
                #self.cnn = torchvision.models.resnet101(pretrained=False)
                self.cnn = resnet.resnet18(pretrained=False, channels=nc)
            elif type=="resnet34":
                self.cnn = resnet.resnet34(pretrained=False, channels=nc)
            elif type=="resnet101":
                self.cnn = resnet.resnet101(pretrained=False, channels=nc)


    def default_CNN(self, nc=3, leakyRelu=False):

        ks = [3, 3, 3, 3, 3, 3, 2] # kernel size 3x3
        ps = [1, 1, 1, 1, 1, 1, 0] # padding
        ss = [1, 1, 1, 1, 1, 1, 1] # stride
        nm = [64, 128, 256, 256, 512, 512, 512] # number of channels/maps

        cnn = nn.Sequential()

        def convRelu(i, batchNormalization=False):
            nIn = nc if i == 0 else nm[i - 1]
            nOut = nm[i]
            cnn.add_module('conv{0}'.format(i),
                           nn.Conv2d(in_channels=nIn, out_channels=nOut, kernel_size=ks[i], stride=ss[i], padding=ps[i]))
            if batchNormalization:
                cnn.add_module('batchnorm{0}'.format(i), nn.BatchNorm2d(nOut))
            if leakyRelu:
                cnn.add_module('relu{0}'.format(i),
                               nn.LeakyReLU(0.2, inplace=True))
            else:
                cnn.add_module('relu{0}'.format(i), nn.ReLU(True))
            #cnn.add_module(f"printAfter{i}", PrintLayer(name=f"printAfter{i}"))

        # input: 16, 1, 60, 256; batch, channels, height, width
        convRelu(0) # 16, 64, 60, 1802
        cnn.add_module('pooling{0}'.format(0), nn.MaxPool2d(2, 2))  # 16, 64, 30, 901
        convRelu(1) # 16, 128, 30, 901
        cnn.add_module('pooling{0}'.format(1), nn.MaxPool2d(2, 2))  # 16, 128, 15, 450
        convRelu(2, True) # 16, 256, 15, 450
        convRelu(3) # 16, 256, 15, 450
        cnn.add_module('pooling{0}'.format(2),
                       nn.MaxPool2d((2, 2), (2, 1), (0, 1)))  # 16, 256, 7, 451 # kernel_size, stride, padding
        convRelu(4, True) # 16, 512, 7, 451
        convRelu(5) # 16, 512, 7, 451
        cnn.add_module('pooling{0}'.format(3),
                       nn.MaxPool2d((2, 2), (2, 1), (0, 1)))  # 16, 512, 3, 452
        convRelu(6, True)  # 16, 512, 2, 451
        return cnn

    """
    0 0 Conv2d(1, 64, kernel_size=(3, 3), stride=(1, 1), padding=(1, 1))
    1 ReLU(inplace)
    2 MaxPool2d(kernel_size=2, stride=2, padding=0, dilation=1, ceil_mode=False)
    3 1 Conv2d(64, 128, kernel_size=(3, 3), stride=(1, 1), padding=(1, 1))
    4 ReLU(inplace)
    5 MaxPool2d(kernel_size=2, stride=2, padding=0, dilation=1, ceil_mode=False)
    6 2 Conv2d(128, 256, kernel_size=(3, 3), stride=(1, 1), padding=(1, 1))
    7 BatchNorm2d(256, eps=1e-05, momentum=0.1, affine=True, track_running_stats=True)
    8 ReLU(inplace)
    9 3 Conv2d(256, 256, kernel_size=(3, 3), stride=(1, 1), padding=(1, 1))
    10 ReLU(inplace)
    11 MaxPool2d(kernel_size=(2, 2), stride=(2, 1), padding=(0, 1), dilation=1, ceil_mode=False)
    12 4 Conv2d(256, 512, kernel_size=(3, 3), stride=(1, 1), padding=(1, 1))
    13 BatchNorm2d(512, eps=1e-05, momentum=0.1, affine=True, track_running_stats=True)
    14 ReLU(inplace)
    15 5 Conv2d(512, 512, kernel_size=(3, 3), stride=(1, 1), padding=(1, 1))
    16 ReLU(inplace)
    17 MaxPool2d(kernel_size=(2, 2), stride=(2, 1), padding=(0, 1), dilation=1, ceil_mode=False)
    18 6 Conv2d(512, 512, kernel_size=(2, 2), stride=(1, 1))
    19 BatchNorm2d(512, eps=1e-05, momentum=0.1, affine=True, track_running_stats=True)
    20 ReLU(inplace)
    """

    def post_process(self, conv):
        b, c, h, w = conv.size() # something like 16, 512, 2, 406
        #print(conv.size())
        conv = conv.view(b, -1, w)  # batch, Height * Channels, Width

        # Width effectively becomes the "time" seq2seq variable
        output = conv.permute(2, 0, 1)  # [w, b, c], first time: [404, 8, 1024] ; second time: 213, 8, 1024
        return output

    def intermediate_process(self, final, intermediate):
        new = self.post_process(self.pool(intermediate))
        final = self.post_process(final)
        return torch.cat([final, new], dim=2)

    def forward(self, input):
        # INPUT: BATCH, CHANNELS (1 or 3), Height, Width
        if self.intermediate_pass is None:
            x = self.post_process(self.cnn(input))
            #assert self.cnnOutSize == x.shape[1] * x.shape[2]
            return x
        else:
            conv = self.cnn[0:self.intermediate_pass](input)
            conv2 = self.cnn[self.intermediate_pass:](conv)
            final = self.intermediate_process(conv2, conv)
            return final

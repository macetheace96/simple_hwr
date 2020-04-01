import numpy as np
import sys
# sys.path.append("../../")
# sys.path.append("../")
# sys.path.append("/media/data/GitHub/simple_hwr")
import os
import numpy as np
from hwr_utils import *
from hwr_utils.stroke_plotting import *
from hwr_utils.stroke_recovery import get_number_of_stroke_pts_from_gt
from hwr_utils.stroke_recovery import *
import json
from matplotlib import pyplot as plt

### POSSIBLY GO BACK TO ORIGINAL HANDLING OF COST_MAT, AND USE cost_mat.base

# Original DTW
# Look at worst match - based on average distance
# Randomly sample among worst matches, based on how bad they are
# Attempt reversing/swapping
# Choose new GT
# Add some buffer
# Choose downstream/upstream baseline points
# Get distance of downstream point
# Refill cost matrix
    # Reuse upstream portion
    # Limit downstream portion
# Traceback
    # Finds new path
    # if better, replace path through window+buffer of original DTW
# Stroke to Dataloader GT
from forbiddenfruit import curse

def push_back(self, a):
    self.append(a)


# list.push_back = push_back

def push_back(self, a):
    self.insert(0, a)


curse(list, "push_back", push_back)

# DTW each stroke iteratively
# DTW until stroke+1 is chosen
# stroke + i is the min of stroke/reverse stroke
# check whether the stroke or reverse stroke does better
INFINITY = 1000


def euclidean_distance(a, b):
    d = 0
    a = np.asarray([a])
    b = np.asarray([b])
    # print(a.shape,b)
    for i in range(a.shape[0]):
        tmp = a[i] - b[i]
        d += tmp * tmp
    return np.sqrt(d)


def d_argmin(a, b, c):
    if a <= b and a <= c:
        return 0
    elif b <= c:
        return 1
    else:
        return 2


def d_min(a, b, c):
    if a < b and a < c:
        return a
    elif b < c:
        return b
    else:
        return c


def traceback_partial(cost_mat, ilen, jlen, imin=0, jmin=0):
    cost = 0.0
    i = ilen - 1
    j = jlen - 1
    #     cdef vector[int] a
    #     cdef vector[int] b
    #     a.push_back(i)
    #     b.push_back(j)

    a = []
    b = []
    a.append(i)
    b.append(j)
    # cdef int match
    while (i > imin or j > jmin):
        match = d_argmin(cost_mat[i - 1, j - 1], cost_mat[i - 1, j], cost_mat[i, j - 1])
        if match == 0:
            i -= 1
            j -= 1
            cost += cost_mat[i - 1, j - 1]
        elif match == 1:
            i -= 1
            cost += cost_mat[i - 1, j]
        else:
            j -= 1
            cost += cost_mat[i, j - 1]
        a.push_back(i)
        b.push_back(j)
    return a, b, cost


def create_cost_mat_2d(a, b, constraint, dist_func=euclidean_distance):
    cost_mat = np.empty((a.shape[0] + 1, b.shape[0] + 1), dtype=np.float64)
    cost_mat[:] = INFINITY
    cost_mat[0, 0] = 0
    for i in range(1, cost_mat.shape[0]):
        for j in range(max(1, i - constraint), min(cost_mat.shape[1], i + constraint + 1)):
            cost_mat[i, j] = dist_func(a[i - 1], b[j - 1]) + \
                             d_min(cost_mat[i - 1, j], cost_mat[i, j - 1], cost_mat[i - 1, j - 1])

    return cost_mat #[1:, 1:]


def traceback(cost_mat, ilen, jlen):
    i = ilen - 1
    j = jlen - 1
    #     cdef vector[int] a
    #     cdef vector[int] b
    #     a.push_back(i)
    #     b.push_back(j)

    cost_mat = cost_mat[1:, 1:]
    cost = cost_mat[i, j]
    a = []
    b = []
    a.append(i)
    b.append(j)
    # cdef int match
    while (i > 0 or j > 0):
        match = d_argmin(cost_mat[i - 1, j - 1], cost_mat[i - 1, j], cost_mat[i, j - 1])
        if match == 0:
            i -= 1
            j -= 1
        elif match == 1:
            i -= 1
        else:
            j -= 1
        a.push_back(i)
        b.push_back(j)
    return a, b, cost

from pydtw import dtw
# Original DTW
# Look at worst match - based on average distance
# Randomly sample among worst matches, based on how bad they are
# Attempt reversing/swapping
# Choose new GT
# Add some buffer
# Choose downstream/upstream baseline points
# Get distance of downstream point
# Refill cost matrix
# Reuse upstream portion
# Limit downstream portion
# Traceback
# Finds new path
# if better, replace path through window+buffer of original DTW
# Stroke to Dataloader GT

"""
for i in range(1, cost_mat.shape[0]):
    for j in range(max(1, i-constraint), min(cost_mat.shape[1], i+constraint+1)):
"""


def refill_cost_matrix(a, b, cost_mat, start_a, end_a, start_b, end_b, constraint, dist_func=euclidean_distance):
    # Include some buffer beyond just the strokes being flipped
    # To get improvement, compare the cost at this point before and after
    # cost_mat = np.empty((a.shape[0] + 1, b.shape[0] + 1), dtype=np.float64)
    # cost_mat[:] = INFINITY
    # cost_mat[0, 0] = 0

    #     start_a = max(start_a - 1, 0)
    #     start_b = max(start_b - 1, 0)
    #     end_a = max(end_a - 1, 0)
    #     end_b = max(end_b - 1, 0)
    cost_mat = cost_mat.base # get the original matrix back
    for i in range(start_a + 1, end_a + 1):
        for j in range(max(start_b + 1, i - constraint), min(end_b + 1, i + constraint + 1)):
            cost_mat[i, j] = dist_func(a[i - 1], b[j - 1]) + \
                            d_min(cost_mat[i - 1, j], cost_mat[i, j - 1], cost_mat[i - 1, j - 1])

    return cost_mat[1:, 1:]


def get_worst_match(gt, preds, a, b, sos):
    """ Return the stroke number with the worst match
    """
    error = abs(gt[a] - preds[b]) ** 2
    print("error", error)
    for x in np.split(gt, sos)[1:]:
        print(x)

    strokes = np.split(error, sos)[1:]

    ## ACTUAL DISTANCE
    if True:
        m = np.sum(np.sum(strokes[-1], axis=1) ** .5)

    x = [np.sum(x) for x in strokes]

    print("average mismatch cost", x)
    return np.argmax(x)


# Try reversing the stroke
# Refill ONLY the stroke of the matrix + end buffer
# Traceback from end buffer
# These are all GT indices
# First ROW/COL of cost matrix are NULL!

gt = np.array(range(36)).reshape(9, 4).astype(np.float64)
gt[:, 2] = [1, 0, 0, 1, 0, 1, 1, 0, 0]

preds = [[8, 9, 1, 3],
         [4, 5, 0, 7],
         [0, 1, 0, 11],
        [12, 13, 1, 15],
        [16, 17, 0, 19],
        [20, 21, 1, 23],
        [32, 33, 1, 27],
         [28, 29, 0, 31],
        [24, 25, 0, 35]]
preds = [[8, 9, 1, 3],
        [4, 5, 0, 7],
        [0, 1, 0, 11],
        [12, 13, 1, 15],
        [16, 17, 0, 19],
        [20, 21, 1, 23],
        [21, 21, 1, 23],
        [32, 33, 1, 27],
        [28, 29, 0, 31],
        [24, 25, 0, 35]]
preds = [[0, 1, 0, 11],
        [4, 5, 0, 7],
        [8, 9, 1, 3],
        [12, 13, 1, 15],
        [16, 17, 0, 19],
        [20, 21, 1, 23],
        [21, 21, 1, 23],
        [32, 33, 1, 27],
        [28, 29, 0, 31],
        [24, 25, 0, 35]]

preds = np.asarray(preds).astype(np.float64)
print(gt)

# traceback(mat, x1.shape[0], x2.shape[0])
# create_cost_mat_2d
# constrained_dtw2d
CONSTRAINT = 5
buffer = 0

cost_mat, costr, a, b = dtw.constrained_dtw2d(np.ascontiguousarray(gt[:, :2]), np.ascontiguousarray(preds[:, :2]),
                                              constraint=CONSTRAINT)
sos = get_sos_args(gt[:, 2], stroke_numbers=False)
worst_match_idx = get_worst_match(gt[:, :2], preds[:, :2], a, b, sos)

# Convert the stroke number to indices in GT
start_idx = sos[worst_match_idx]
start_idx_buffer = max(start_idx - buffer, 0)  # double check -1
end_idx = gt.shape[0] if worst_match_idx + 1 >= sos.size or sos[worst_match_idx] > gt.size else sos[worst_match_idx + 1]
end_idx_buffer = gt.shape[0] if worst_match_idx + 1 >= sos.size or sos[worst_match_idx] + buffer > gt.size else sos[worst_match_idx] + buffer

# Reverse the line
_start_idx = start_idx if start_idx != 0 else None
new_gt = gt[end_idx-1:_start_idx:-1, :2]

# Old Cost
if end_idx_buffer:
    alignment_end_idx = np.argmax(a == end_idx_buffer)  # first GT point
    old_cost = cost_mat[a[alignment_end_idx], b[alignment_end_idx]]  # where we will start the traceback later
else:
    old_cost = cost_mat[a[-1], b[-1]]

# Refill
cost_mat = refill_cost_matrix(a, b, cost_mat, start_idx, end_idx, start_idx, end_idx, constraint=CONSTRAINT, dist_func=euclidean_distance)
print(cost_mat)

# Traceback
    # Finds new path
    # if better, replace path through window+buffer of original DTW
import math


def in_range(k: int, r: int) -> bool:
    return k >= r > 0


def CP_at_1k(r: int, k: int, **kwargs) -> float:
    """
    Context Precision @ 1K
    This is equivalent to the reciprocal rank RR@K

    r = rank of the desired item. 1 based
    k = number of top item of the results set
    """
    return 1.0 / r if in_range(k, r) else 0.0


def Ps_at_1k(r: int, k: int, **kwargs) -> int:
    """
    Presence @ 1k

    r = rank of the desired item, 1 based
    k = number of top item of the results set
    """
    return 1 if in_range(k, r) else 0


def NP_at_1k(r: int, k: int, **kwargs) -> int:
    """
    No Presence @ 1k

    r = rank of the desired item, 1 based
    k = number of top item of the results set
    """
    return 0 if in_range(k, r) else 1


def lzp_at_1k(r: int, k: int, **kwargs) -> float:
    """
    Linear Zero Position @ 1k

    r = rank of the desired item, 1 based
    k = results set size
    """
    return (1.0 - (r - 1) / k) if in_range(k, r) else 0.0


def ezp_at_1k(r: int, k: int, s: float = 3, **kwargs) -> float:
    """
    Exponential Zero Position @ k

    r = rank of the desired item. 1 based
    k = results set size
    s = curvature scaling constant. default to 1/3
    """

    return (
        (math.exp((k - r + 1) / s) - 1) / (math.exp(k / s) - 1)
        if in_range(k, r)
        else 0.0
    )


def lep_at_1k(r: int, e: int, k: int, **kwargs) -> float:
    """
    Linear Expected Position @ k

    r = actual rank of the desired item. 1 based
    e = expected rank of the desired item
    k = results set size
    """
    return (1.0 - abs(e - r) / k) if in_range(k, r) else 0.0


def eep_at_1k(r: int, e: int, k: int, s: float = 3, **kwargs) -> float:
    """
    Exponential Zero Position @ k

    r = actual rank of the desired item
    e = expected rank of the desired item
    k = results set size
    s = curvature scaling constant. default to 1/3
    """
    return (
        (math.exp((k - abs(e - r)) / s) - 1) / (math.exp(k / s) - 1)
        if in_range(k, r)
        else 0.0
    )


def RR_at_1k(r: int, k: int, **kwargs) -> float:
    """
    Reciprocal rank at K

    r = rank of the desired item
    k = results set size
    """
    return 1.0 / r if in_range(k, r) else 0.0


def znDCG_at_1k(r: int, k: int, **kwargs) -> float:
    """
    zero normalized Discounted Cumulative Gain at 1K

    r = rank of the desired item, 1 based
    k = results set size
    """
    return 1.0 / math.log2(r + 1) if in_range(k, r) else 0.0


def enDCG_at_1k(r: int, e: int, k: int, **kwargs) -> float:
    """
    expected normalized Discounted Cumulative Gain at 1K

    r = actual rank of the desired item,
    e = expected rank of the desired item
    k = results set size
    """
    return math.log2(e + 1) / math.log2(r + 1) if in_range(k, r) else 0.0


def EP_at_1k(ag: str, eg: str, wm: dict, **kwargs) -> float:
    """
    Extended Presence at 1K

    ag = actual group the document should belong to. Allowed groups: HR, LR, NP
    eg = expected group the document should belong to. Allowed groups: HR, LR, NP
    wm = dictionary containing the weights matrix
    """
    return wm[ag + "," + eg]


def compare_rank_for_CxP(r1, r2, k) -> int:
    """
    compare the relative rank of two documents

    r1 = rank of more relevant document
    r2 = rank of less relevant document
    k = results set size
    """
    return 1 if r1 > 0 and r1 <= k and r2 > 0 and r2 <= k and r1 < r2 else 0


def CRP_at_k(r: list[int], k: int, **kwargs) -> float:
    """
    Comparative Relative Presence at K
    The value of the metric is the percentage of documents that are in the correct order

    r = list of ranks of the targeted documents in the expected order
    k = results set size
    """
    max_i = len(r) - 1
    return (
        1.0
        * sum([compare_rank_for_CxP(r[i], r[i + 1], k) for i in range(max_i)])
        / (max_i)
    )


def CAP_at_k(r: list[int], k: int, **kwargs) -> float:
    """
    Comparative Absolute Presence at K
    The value of the metric is 1 if all documents are in the correct order,
    0 otherwise

    r = list of ranks of the targeted documents in the expected order
    k = results set size
    """
    return float(
        all([compare_rank_for_CxP(r[i], r[i + 1], k) for i in range(len(r) - 1)])
    )


metrics_at_1k = {
    "CP_at_1k": CP_at_1k,
    "Context_Precision_at_1k": CP_at_1k,
    "Ps_at_1k": Ps_at_1k,
    "Presence_at_1k": Ps_at_1k,
    "lzp_at_1k": lzp_at_1k,
    "linear_zero_precision_at_1k": lzp_at_1k,
    "ezp_at_1k": ezp_at_1k,
    "exponential_zero_precision_at_1k": ezp_at_1k,
    "lep_at_1k": lep_at_1k,
    "linear_expected_precision_at_1k": lep_at_1k,
    "eep_at_1k": eep_at_1k,
    "exponential_expected_precision_at_1k": eep_at_1k,
    "RR_at_1k": RR_at_1k,
    "Reciprocal_Rank_at_1k": RR_at_1k,
    "znDCG_at_1k": znDCG_at_1k,
    "zero_normalized_Discounted_Cumulative_Gain_at_1k": znDCG_at_1k,
    "enDCG_at_1k": enDCG_at_1k,
    "expected_normalized_Discounted_Cumulative_Gain_at_1k": enDCG_at_1k,
    "EP_at_1k": EP_at_1k,
    "extended_presence_at_1k": EP_at_1k,
    "CRP_at_k": CRP_at_k,
    "comparative_relative_presence_at_k": CRP_at_k,
    "CAP_at_k": CAP_at_k,
    "comparative_absolute_presence_at_k": CAP_at_k,
}

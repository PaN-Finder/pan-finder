import math

in_range = lambda k, r: k >= r > 0


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

    ar = actual rank of the desired item. 1 based
    er = expected rank of the desired item
    k = results set size
    """
    return (1.0 - abs(e - r) / k) if in_range(k, r) else 0.0


def eep_at_1k(r: int, e: int, k: int, s: float = 3, **kwargs) -> float:
    """
    Exponential Zero Position @ k

    ar = actual rank of the desired item
    er = expected rank of the desired item
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

    ar = actual rank of the desired item,
    er = expected rank of the desired item
    k = results set size
    """
    return math.log2(e + 1) / math.log2(r + 1) if in_range(k, r) else 0.0


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
}

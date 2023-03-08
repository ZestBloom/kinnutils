import time
from functools import wraps


def time_it(logger=None):
    def deco_time_it(func):
        @wraps(func)
        def inner(*arg, **kwargs):
            starttime = time.time()
            result = func(*arg, **kwargs)
            endtime = time.time()

            if logger is not None:
                logger.info(
                    f"Called {func.__name__}",
                    func=func.__name__,
                    elapsed=(endtime - starttime),
                )
            return result

        return inner

    return deco_time_it


def retry(ExceptionToCheck, tries=4, delay=3, backoff=2, logger=None):
    """Retry calling the decorated function using an exponential backoff.

    :param ExceptionToCheck: the exception to check. may be a tuple of
        exceptions to check
    :type ExceptionToCheck: Exception or tuple
    :param tries: number of times to try (not retry) before giving up
    :type tries: int
    :param delay: initial delay between retries in seconds
    :type delay: int
    :param backoff: backoff multiplier e.g. value of 2 will double the delay
        each retry
    :type backoff: int
    :param logger: logger to use. If None, print
    :type logger: logging.Logger instance
    """

    def deco_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except ExceptionToCheck as e:
                    msg = f"Failed, Retrying in {mdelay}s"
                    if logger:
                        logger.warning(
                            msg, exception=type(e).__name__, function=f.__name__
                        )
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)

        return f_retry  # true decorator

    return deco_retry

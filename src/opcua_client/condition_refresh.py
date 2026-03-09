from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

from asyncua import ua


async def condition_refresh_with_retry(
    server_node,
    subscription_id: int,
    logger: logging.Logger,
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    is_active: Optional[Callable[[], bool]] = None,
) -> None:
    """Call the ConditionRefresh method with simple retry/backoff.

    This is best-effort and never raises. It is intentionally conservative:
    - Transport-level errors (timeouts, connection resets, "Failed to send request")
      are treated as retryable up to ``max_attempts``.
    - Obvious UA-level configuration errors (e.g. BadNoSubscription) are treated as
      non-retryable and abort immediately.
    """

    for attempt in range(1, max_attempts + 1):
        if is_active is not None and not is_active():
            logger.info(
                "Skipping ConditionRefresh for SubscriptionId=%s: client or subscription no longer active",
                subscription_id,
            )
            return

        try:
            logger.info(
                "ConditionRefresh attempt %s/%s for SubscriptionId=%s",
                attempt,
                max_attempts,
                subscription_id,
            )
            await server_node.call_method(
                ua.ObjectIds.ConditionType_ConditionRefresh,
                ua.Variant(subscription_id, ua.VariantType.UInt32),
            )
            logger.info(
                "ConditionRefresh succeeded for SubscriptionId=%s on attempt %s",
                subscription_id,
                attempt,
            )
            return

        except ua.UaError as exc:
            status = getattr(exc, "status", None)
            status_name = getattr(status, "name", None) or str(status) if status is not None else type(exc).__name__

            if status == ua.StatusCodes.BadNoSubscription:
                logger.warning(
                    "ConditionRefresh aborted for SubscriptionId=%s: subscription no longer exists (status=%s)",
                    subscription_id,
                    status_name,
                )
                return

            logger.warning(
                "ConditionRefresh failed with UA error (non-retryable) on attempt %s/%s for SubscriptionId=%s: %r",
                attempt,
                max_attempts,
                subscription_id,
                exc,
            )
            return

        except (OSError, asyncio.TimeoutError, ConnectionError) as exc:
            logger.warning(
                "ConditionRefresh transport failure on attempt %s/%s for SubscriptionId=%s: %r",
                attempt,
                max_attempts,
                subscription_id,
                exc,
            )

        except Exception as exc:  # pragma: no cover - defensive catch-all
            message = str(exc)
            if "Failed to send request" in message:
                logger.warning(
                    "ConditionRefresh transport-style failure on attempt %s/%s for SubscriptionId=%s: %r",
                    attempt,
                    max_attempts,
                    subscription_id,
                    exc,
                )
            else:
                logger.warning(
                    "ConditionRefresh failed with unexpected error (non-retryable) on attempt %s/%s for SubscriptionId=%s: %r",
                    attempt,
                    max_attempts,
                    subscription_id,
                    exc,
                )
                return

        if attempt >= max_attempts:
            logger.warning(
                "ConditionRefresh ultimately failed after %s attempts for SubscriptionId=%s",
                attempt,
                subscription_id,
            )
            return

        delay = min(base_delay * (2 ** (attempt - 1)), 10.0)
        logger.info(
            "Retrying ConditionRefresh for SubscriptionId=%s in %.1fs (attempt %s/%s)",
            subscription_id,
            delay,
            attempt + 1,
            max_attempts,
        )
        await asyncio.sleep(delay)


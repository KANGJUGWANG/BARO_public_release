from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from datetime import date

from playwright.async_api import Browser, Page, TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from crawler.constants import (
    CARD_SELECTORS,
    INTERCEPT,
    PLAYWRIGHT_LAUNCH_ARGS,
    PLAYWRIGHT_LOCALE,
    PLAYWRIGHT_TIMEZONE,
    PLAYWRIGHT_VIEWPORT,
)
from crawler.parser import extract_cards, parse_chunks
from crawler.url_builder import build_url

log = logging.getLogger(__name__)
if not log.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    log.addHandler(handler)
log.setLevel(logging.INFO)
log.propagate = False

GOTO_TIMEOUT_MS = 60_000
RESPONSE_WAIT_MS = 30_000
CARD_BODY_TIMEOUT_S = 30.0
CARD_PROCESS_TIMEOUT_S = 60.0
GO_BACK_TIMEOUT_MS = 4_000
ROUNDTRIP_SOFT_BUDGET_S = 165.0
MIN_REMAINING_SECONDS = 3.0


def _brief_exc(exc: Exception) -> str:
    text = str(exc).replace("\n", " ").strip()
    return text[:300] if text else exc.__class__.__name__


class CrawlError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


async def _wait_for_response(
    page: Page,
    min_ms: int = 2_000,
    networkidle_timeout: int = 10_000,
) -> None:
    await page.wait_for_timeout(min_ms)
    try:
        await page.wait_for_load_state("networkidle", timeout=networkidle_timeout)
    except Exception:
        pass


async def _get_card_els(page: Page) -> list:
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(1_200)
    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(400)

    for selector in CARD_SELECTORS:
        els = await page.query_selector_all(selector)
        if els:
            return els

    return []


async def collect_oneway_realtime(
    origin: str,
    dest: str,
    dep_date: date,
) -> list[dict]:
    tag = f"OW {origin}->{dest} {dep_date}"
    url = build_url(dep_date, None, origin, dest)
    texts: list[str] = []
    intercept_count = 0
    total_response_count = 0
    flight_response_count = 0
    request_failed_count = 0
    status_counts: Counter[int | str] = Counter()

    async def capture(resp) -> None:
        nonlocal flight_response_count, intercept_count, total_response_count
        total_response_count += 1
        status_counts[resp.status] += 1

        if "google.com/travel/flights" in resp.url:
            flight_response_count += 1
            log.debug("[%s] flight response: %s (status=%s)", tag, resp.url[:150], resp.status)

        if INTERCEPT in resp.url:
            intercept_count += 1
            log.info("[%s] intercept hit: %s", tag, resp.url[:150])
            try:
                body = await resp.body()
                texts.append(body.decode("utf-8", errors="replace"))
            except Exception:
                pass
        elif "/travel/" in resp.url or "googleapis" in resp.url:
            log.debug("[%s] non-intercept travel response: %s", tag, resp.url[:150])

    def capture_request_failed(req) -> None:
        nonlocal request_failed_count
        request_failed_count += 1
        failure = req.failure or "unknown"
        log.warning("[%s] request failed: %s %s", tag, req.url[:200], failure)

    log.info("[%s] request url: %s", tag, url)
    goto_elapsed = 0.0

    try:
        async with async_playwright() as playwright:
            try:
                browser = await playwright.chromium.launch(
                    headless=True,
                    args=PLAYWRIGHT_LAUNCH_ARGS,
                )
            except Exception as exc:
                log.warning(
                    "[%s] browser launch failed: %s",
                    tag,
                    exc.__class__.__name__,
                )
                log.warning("[%s] final error reason: browser launch failed", tag)
                raise CrawlError("browser launch failed") from exc
            log.info("[%s] browser launched", tag)

            try:
                ctx = await browser.new_context(
                    locale=PLAYWRIGHT_LOCALE,
                    timezone_id=PLAYWRIGHT_TIMEZONE,
                    viewport=PLAYWRIGHT_VIEWPORT,
                    extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"},
                )
                log.info("[%s] context created", tag)
                page = await ctx.new_page()
                log.info("[%s] page created", tag)
                page.on("response", capture)
                page.on("requestfailed", capture_request_failed)

                try:
                    start = time.perf_counter()
                    log.info("[%s] goto started", tag)
                    try:
                        await page.goto(
                            url,
                            wait_until="commit",
                            timeout=GOTO_TIMEOUT_MS,
                        )
                    except PlaywrightTimeoutError as exc:
                        goto_elapsed = time.perf_counter() - start
                        log.warning(
                            "[%s] goto timeout after %.2f seconds: %s",
                            tag,
                            goto_elapsed,
                            _brief_exc(exc),
                        )
                        log.warning(
                            "[%s] page goto timeout, continue waiting for intercepted responses",
                            tag,
                        )
                    except Exception as exc:
                        goto_elapsed = time.perf_counter() - start
                        log.warning(
                            "[%s] page goto failed after %.2f seconds: %s",
                            tag,
                            goto_elapsed,
                            _brief_exc(exc),
                        )
                        log.warning(
                            "[%s] page goto failed, continue waiting for intercepted responses",
                            tag,
                        )
                    else:
                        goto_elapsed = time.perf_counter() - start
                        log.info(
                            "[%s] goto result: committed after %.2f seconds",
                            tag,
                            goto_elapsed,
                        )

                    try:
                        title = await page.title()
                        log.info("[%s] page title: %s", tag, title[:100])
                        log.info("[%s] page url: %s", tag, page.url[:200])
                    except Exception:
                        pass

                    log.info("[%s] wait responses started", tag)
                    await _wait_for_response(
                        page,
                        min_ms=RESPONSE_WAIT_MS,
                        networkidle_timeout=5_000,
                    )
                    try:
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await page.wait_for_timeout(1_000)
                    except Exception as exc:
                        log.warning("[%s] page scroll skipped: %s", tag, _brief_exc(exc))
                finally:
                    page.remove_listener("response", capture)
                    page.remove_listener("requestfailed", capture_request_failed)
                    await ctx.close()
            finally:
                await browser.close()
    except CrawlError:
        raise
    except Exception as exc:
        log.warning("[%s] realtime crawl failed: %s", tag, _brief_exc(exc))
        log.warning("[%s] final error reason: crawling failed", tag)
        raise CrawlError("crawling failed") from exc

    log.info("[%s] total response count: %s", tag, total_response_count)
    log.info("[%s] google/travel/flights response count: %s", tag, flight_response_count)
    log.info("[%s] intercept response count: %s", tag, intercept_count)
    log.info("[%s] request failed count: %s", tag, request_failed_count)
    log.info("[%s] response status summary: %s", tag, dict(status_counts))
    log.info("[%s] response body count: %s", tag, len(texts))

    if intercept_count == 0:
        log.warning("[%s] final error reason: no flight data", tag)
        raise CrawlError("no flight data")
    if not texts:
        log.warning("[%s] final error reason: no response body", tag)
        raise CrawlError("no response body")

    try:
        cards: list[dict] = []
        chunk_count = 0
        for text in texts:
            chunks = parse_chunks(text)
            chunk_count += len(chunks)
            for chunk in chunks:
                if chunk["inner"]:
                    cards.extend(extract_cards(chunk["inner"]))
    except Exception as exc:
        log.warning("[%s] parsing failed: %s", tag, _brief_exc(exc))
        log.warning("[%s] final error reason: parse failed", tag)
        raise CrawlError("parse failed") from exc

    log.info("[%s] parsed chunk count: %s", tag, chunk_count)
    log.info("[%s] extracted card count: %s", tag, len(cards))

    if chunk_count == 0:
        log.warning("[%s] final error reason: parse failed", tag)
        raise CrawlError("parse failed")
    if not cards:
        log.warning("[%s] final error reason: no cards", tag)
        raise CrawlError("no cards")

    seen: set[str] = set()
    unique: list[dict] = []

    for card in cards:
        flight_no = (card.get("dep") or {}).get("flight_no")
        if not flight_no:
            unique.append(card)
            continue
        if flight_no not in seen:
            seen.add(flight_no)
            unique.append(card)

    log.info("[%s] returned offer count: %s", tag, len(unique))
    if not unique:
        log.warning("[%s] final error reason: no cards", tag)
        raise CrawlError("no cards")

    return unique


async def _process_roundtrip_card(
    page: Page,
    card_el,
    outbound: dict,
    card_idx: int,
    tag: str,
    stats: dict,
    body_timeout_s: float = CARD_BODY_TIMEOUT_S,
) -> list[dict]:
    texts: list[str] = []
    outbound_dep = outbound.get("dep") or {}
    outbound_flight_no = outbound_dep.get("flight_no") or "?"
    outbound_dep_time = outbound_dep.get("dep_time") or ""
    outbound_airline_name = outbound.get("airline_name") or ""

    def to_display_time(value: str) -> str:
        if not value or ":" not in value:
            return value
        try:
            hour, minute = map(int, value.split(":"))
        except ValueError:
            return value
        period = "오전" if hour < 12 else "오후"
        display_hour = hour if hour <= 12 else hour - 12
        if display_hour == 0:
            display_hour = 12
        return f"{period} {display_hour}:{minute:02d}"

    try:
        card_text = await card_el.inner_text()
        if outbound_airline_name and to_display_time(outbound_dep_time) not in card_text:
            log.warning("[%s] roundtrip card text mismatch: %s", tag, outbound_flight_no)
    except Exception:
        pass

    try:
        await card_el.scroll_into_view_if_needed()
        async with page.expect_response(lambda resp: INTERCEPT in resp.url, timeout=10_000) as resp_info:
            await card_el.click()

        first = await resp_info.value
        try:
            body = await asyncio.wait_for(first.body(), timeout=body_timeout_s)
            texts.append(body.decode("utf-8", errors="replace"))
        except asyncio.TimeoutError:
            stats["response_body_timeout_count"] += 1
            log.warning("[%s] card %d response body timeout (%.1fs)", tag, card_idx, body_timeout_s)
        except Exception:
            pass
    except Exception as exc:
        log.debug("[%s] roundtrip card click skipped: %s %s", tag, card_idx, _brief_exc(exc))
        try:
            await page.go_back(timeout=GO_BACK_TIMEOUT_MS)
            await page.wait_for_load_state("domcontentloaded", timeout=GO_BACK_TIMEOUT_MS)
        except Exception:
            pass
        return []

    async def capture_extra(resp) -> None:
        if INTERCEPT in resp.url:
            try:
                body = await asyncio.wait_for(resp.body(), timeout=body_timeout_s)
                texts.append(body.decode("utf-8", errors="replace"))
            except asyncio.TimeoutError:
                stats["response_body_timeout_count"] += 1
                log.warning("[%s] card %d extra response body timeout (%.1fs)", tag, card_idx, body_timeout_s)
            except Exception:
                pass

    page.on("response", capture_extra)
    try:
        await _wait_for_response(page, min_ms=500, networkidle_timeout=5_000)
    finally:
        page.remove_listener("response", capture_extra)

    ret_cards: list[dict] = []
    for text in texts:
        for chunk in parse_chunks(text):
            if chunk["inner"]:
                ret_cards.extend(extract_cards(chunk["inner"]))

    outbound_airline_code = outbound.get("airline_code")
    same_airline = [card for card in ret_cards if card.get("airline_code") == outbound_airline_code]

    try:
        await page.go_back(timeout=GO_BACK_TIMEOUT_MS)
        await page.wait_for_load_state("domcontentloaded", timeout=GO_BACK_TIMEOUT_MS)
    except Exception:
        pass

    combos: list[dict] = []
    for inbound in same_airline:
        inbound_dep = inbound.get("dep") or {}
        seller = inbound.get("official_seller") or {}
        combos.append(
            {
                "outbound_flight_no": outbound_dep.get("flight_no"),
                "outbound_dep_time": outbound_dep.get("dep_time"),
                "outbound_arr_time": outbound_dep.get("arr_time"),
                "outbound_dep_date": outbound_dep.get("dep_date"),
                "outbound_duration_min": outbound_dep.get("duration_min"),
                "airline_code": outbound.get("airline_code"),
                "airline_name": outbound.get("airline_name"),
                "inbound_airline_code": inbound.get("airline_code"),
                "inbound_airline_name": inbound.get("airline_name"),
                "inbound_flight_no": inbound_dep.get("flight_no"),
                "inbound_dep_time": inbound_dep.get("dep_time"),
                "inbound_arr_time": inbound_dep.get("arr_time"),
                "inbound_dep_date": inbound_dep.get("dep_date"),
                "inbound_duration_min": inbound_dep.get("duration_min"),
                "price_krw": inbound.get("price_krw"),
                "outbound_ref_price": outbound.get("price_krw"),
                "official_seller": seller,
                "stops": outbound.get("stops", 0),
                "aircraft": outbound_dep.get("aircraft"),
                "airline_tag_present": outbound.get("airline_tag_present", False),
                "seller_type": inbound.get("seller_type") or outbound.get("seller_type") or "unknown",
            }
        )
    return combos


async def _recover_roundtrip_page(page: Page, search_url: str | None = None, tag: str = "") -> bool:
    try:
        await page.go_back(timeout=GO_BACK_TIMEOUT_MS)
        await page.wait_for_load_state("domcontentloaded", timeout=GO_BACK_TIMEOUT_MS)
        return True
    except Exception as exc:
        log.debug("[%s] go_back recovery skipped: %s", tag, _brief_exc(exc))

    if search_url:
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=10_000)
            await _wait_for_response(page, min_ms=500, networkidle_timeout=3_000)
            return True
        except Exception as exc:
            log.warning("[%s] goto recovery failed: %s", tag, _brief_exc(exc))

    return False


async def _collect_roundtrip_with_browser(
    browser: Browser,
    origin: str,
    dest: str,
    dep_date: date,
    ret_date: date,
    max_outbound_cards: int = 33,
    max_combos: int = 200,
    card_timeout_s: float = CARD_PROCESS_TIMEOUT_S,
    body_timeout_s: float = CARD_BODY_TIMEOUT_S,
    soft_budget_seconds: float = ROUNDTRIP_SOFT_BUDGET_S,
) -> tuple[str, list[dict], dict]:
    tag = f"RT {origin}<->{dest} {dep_date}"
    url = build_url(dep_date, ret_date, origin, dest)
    stage1_raw: list[str] = []
    started = time.monotonic()
    deadline = started + soft_budget_seconds
    stats = {
        "processed_card_count": 0,
        "failed_card_count": 0,
        "skipped_card_count": 0,
        "card_timeout_count": 0,
        "response_body_timeout_count": 0,
        "combo_count": 0,
        "elapsed_seconds": 0.0,
        "soft_budget_exhausted": False,
        "target_combo_reached": False,
        "recovery_failed_count": 0,
    }

    async def capture_stage1(resp) -> None:
        if INTERCEPT in resp.url:
            try:
                body = await resp.body()
                stage1_raw.append(body.decode("utf-8", errors="replace"))
            except Exception:
                pass

    ctx = await browser.new_context(
        locale=PLAYWRIGHT_LOCALE,
        timezone_id=PLAYWRIGHT_TIMEZONE,
        viewport=PLAYWRIGHT_VIEWPORT,
        extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"},
    )
    try:
        page = await ctx.new_page()
        page.on("response", capture_stage1)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT_MS)
            await _wait_for_response(page, min_ms=2_000, networkidle_timeout=10_000)
        except Exception as exc:
            log.warning("[%s] roundtrip stage1 crawl failed: %s", tag, _brief_exc(exc))
            raise CrawlError("roundtrip stage1 crawl failed") from exc
        finally:
            page.remove_listener("response", capture_stage1)

        stage1_cards: list[dict] = []
        for text in stage1_raw:
            for chunk in parse_chunks(text):
                if chunk["inner"]:
                    stage1_cards.extend(extract_cards(chunk["inner"]))

        seen: set[str] = set()
        outbound_unique: list[dict] = []
        for card in stage1_cards:
            flight_no = (card.get("dep") or {}).get("flight_no")
            if flight_no and flight_no not in seen:
                seen.add(flight_no)
                outbound_unique.append(card)

        log.info("[%s] outbound card count: %s", tag, len(outbound_unique))
        log.info(
            "[%s] bounded: max_cards=%d max_combos=%d total_outbound=%d",
            tag,
            max_outbound_cards,
            max_combos,
            len(outbound_unique),
        )

        all_combos: list[dict] = []
        cards_to_process = outbound_unique[:max_outbound_cards]
        for index, outbound in enumerate(cards_to_process):
            if len(all_combos) >= max_combos:
                log.info(
                    "[%s] combo limit reached: %d >= %d, early stop",
                    tag,
                    len(all_combos),
                    max_combos,
                )
                break

            remaining = deadline - time.monotonic()
            if remaining <= MIN_REMAINING_SECONDS:
                stats["soft_budget_exhausted"] = True
                log.info("[%s] soft budget exhausted; stop card loop", tag)
                break

            card_els = await _get_card_els(page)
            if index >= len(card_els):
                stats["skipped_card_count"] += 1
                continue

            per_card_timeout = min(card_timeout_s, max(1.0, remaining))
            try:
                combos = await asyncio.wait_for(
                    _process_roundtrip_card(
                        page,
                        card_els[index],
                        outbound,
                        index,
                        tag,
                        stats,
                        body_timeout_s=body_timeout_s,
                    ),
                    timeout=per_card_timeout,
                )
                remaining_combo_slots = max_combos - len(all_combos)
                limited_combos = combos[:remaining_combo_slots]
                all_combos.extend(limited_combos)
                stats["processed_card_count"] += 1
                log.info(
                    "[%s] card %d done: got %d combos, added %d (total=%d)",
                    tag,
                    index,
                    len(combos),
                    len(limited_combos),
                    len(all_combos),
                )
            except asyncio.TimeoutError:
                stats["card_timeout_count"] += 1
                stats["failed_card_count"] += 1
                log.warning("[%s] card %d timeout after %.1fs", tag, index, per_card_timeout)
                recovered = await _recover_roundtrip_page(page, url, tag)
                if not recovered:
                    stats["recovery_failed_count"] += 1
                    break
            except Exception as exc:
                stats["failed_card_count"] += 1
                log.warning("[%s] card %d failed: %s", tag, index, _brief_exc(exc))
                recovered = await _recover_roundtrip_page(page, url, tag)
                if not recovered:
                    stats["recovery_failed_count"] += 1
                    break

            if len(all_combos) >= max_combos:
                stats["target_combo_reached"] = True
                log.info(
                    "[%s] combo limit reached after card %d: total=%d max=%d",
                    tag,
                    index,
                    len(all_combos),
                    max_combos,
                )
                break
    finally:
        await ctx.close()

    seen_combo: set[tuple] = set()
    unique: list[dict] = []
    for combo in all_combos:
        key = (combo.get("outbound_flight_no"), combo.get("inbound_flight_no"))
        if key not in seen_combo:
            seen_combo.add(key)
            unique.append(combo)

    stats["combo_count"] = len(unique)
    stats["elapsed_seconds"] = round(time.monotonic() - started, 2)
    log.info("[%s] roundtrip combo count: %s", tag, len(unique))
    log.info("[%s] card stats: %s", tag, stats)
    return url, unique, stats


async def collect_roundtrip_realtime(
    origin: str,
    dest: str,
    dep_date: date,
    ret_date: date,
    max_outbound_cards: int = 33,
    max_combos: int = 200,
    card_timeout_s: float = CARD_PROCESS_TIMEOUT_S,
    body_timeout_s: float = CARD_BODY_TIMEOUT_S,
    soft_budget_seconds: float = ROUNDTRIP_SOFT_BUDGET_S,
) -> dict:
    tag = f"RT {origin}<->{dest} {dep_date}/{ret_date}"
    log.info("[%s] roundtrip realtime crawl started", tag)
    try:
        async with async_playwright() as playwright:
            try:
                browser = await playwright.chromium.launch(
                    headless=True,
                    args=PLAYWRIGHT_LAUNCH_ARGS,
                )
            except Exception as exc:
                log.warning("[%s] browser launch failed: %s", tag, exc.__class__.__name__)
                raise CrawlError("browser launch failed") from exc
            try:
                _, combos, stats = await _collect_roundtrip_with_browser(
                    browser,
                    origin,
                    dest,
                    dep_date,
                    ret_date,
                    max_outbound_cards=max_outbound_cards,
                    max_combos=max_combos,
                    card_timeout_s=card_timeout_s,
                    body_timeout_s=body_timeout_s,
                    soft_budget_seconds=soft_budget_seconds,
                )
            finally:
                await browser.close()
    except CrawlError:
        raise
    except Exception as exc:
        log.warning("[%s] roundtrip realtime crawl failed: %s", tag, _brief_exc(exc))
        raise CrawlError("roundtrip crawling failed") from exc

    return {"combos": combos, "stats": stats}

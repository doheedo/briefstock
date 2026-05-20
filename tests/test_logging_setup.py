import logging

import httpx

from daily_stock_briefing.jobs.run_daily_briefing import configure_logging


def test_configure_logging_writes_to_file(tmp_path):
    log_file = tmp_path / "briefstock.log"
    logger_name = "daily_stock_briefing.tests.file_logging"

    configure_logging(log_file=log_file)
    logging.getLogger(logger_name).error("file logging works")
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert log_file.is_file()
    assert "file logging works" in log_file.read_text(encoding="utf-8")


def test_configure_logging_redacts_telegram_bot_token_from_urls(tmp_path):
    log_file = tmp_path / "briefstock.log"
    bot_token = "123456:secret-token"

    configure_logging(log_file=log_file)
    logging.getLogger("httpx").info(
        'HTTP Request: POST %s "HTTP/1.1 200 OK"',
        f"https://api.telegram.org/bot{bot_token}/sendDocument",
    )
    for handler in logging.getLogger().handlers:
        handler.flush()

    log_text = log_file.read_text(encoding="utf-8")
    assert bot_token not in log_text
    assert "https://api.telegram.org/bot<redacted>/sendDocument" in log_text


def test_configure_logging_redacts_telegram_bot_token_from_httpx_url_args(tmp_path):
    log_file = tmp_path / "briefstock.log"
    bot_token = "123456:secret-token"

    configure_logging(log_file=log_file)
    logging.getLogger("httpx").info(
        'HTTP Request: POST %s "HTTP/1.1 200 OK"',
        httpx.URL(f"https://api.telegram.org/bot{bot_token}/sendMessage"),
    )
    for handler in logging.getLogger().handlers:
        handler.flush()

    log_text = log_file.read_text(encoding="utf-8")
    assert bot_token not in log_text
    assert "https://api.telegram.org/bot<redacted>/sendMessage" in log_text

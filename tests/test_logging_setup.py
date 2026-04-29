import logging

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

"""CLI entrypoint coverage."""

from unittest.mock import patch

from financial_tracker_api.main import main


def test_main_starts_uvicorn() -> None:
    with patch("uvicorn.run") as run:
        main()
        run.assert_called_once()
        assert run.call_args.args[0] == "financial_tracker_api.main:app"

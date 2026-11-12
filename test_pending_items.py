import unittest
from unittest.mock import AsyncMock, Mock, patch

from utils.pending_items import _navigate_pager, _wait_for_page_change


class PendingItemsPaginationTest(unittest.IsolatedAsyncioTestCase):
    @patch("utils.pending_items.asyncio.sleep", new_callable=AsyncMock)
    @patch("utils.pending_items._page_signature", new_callable=AsyncMock)
    async def test_waits_until_ajax_changes_the_grid(self, signature_mock, sleep_mock):
        signature_mock.side_effect = ["old-page", "new-page"]

        result = await _wait_for_page_change(Mock(), "old-page", timeout_ms=1000)

        self.assertEqual(result, "new-page")
        self.assertEqual(sleep_mock.await_count, 2)

    @patch("utils.pending_items._click_pager", new_callable=AsyncMock)
    @patch("utils.pending_items.asyncio.sleep", new_callable=AsyncMock)
    @patch("utils.pending_items._page_signature", new_callable=AsyncMock)
    async def test_navigation_does_not_continue_with_stale_rows(
        self,
        signature_mock,
        sleep_mock,
        click_mock,
    ):
        signature_mock.side_effect = ["page-1", "page-1", "page-2"]
        click_mock.return_value = True

        changed = await _navigate_pager(Mock(), "next")

        self.assertTrue(changed)
        click_mock.assert_awaited_once()
        self.assertEqual(sleep_mock.await_count, 2)

    @patch("utils.pending_items.asyncio.sleep", new_callable=AsyncMock)
    @patch("utils.pending_items._page_signature", new_callable=AsyncMock)
    async def test_page_change_times_out_when_grid_stays_equal(
        self,
        signature_mock,
        sleep_mock,
    ):
        signature_mock.return_value = "same-page"

        result = await _wait_for_page_change(Mock(), "same-page", timeout_ms=400)

        self.assertIsNone(result)
        self.assertEqual(sleep_mock.await_count, 2)


if __name__ == "__main__":
    unittest.main()

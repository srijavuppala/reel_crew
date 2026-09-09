import inspect
import unittest


class EventLoopContractTests(unittest.TestCase):
    def test_search_endpoint_is_synchronous(self):
        """The workflow blocks on Gemini and on the MCP subprocess. Declaring the
        handler `async def` puts that blocking work on the event loop and
        serialises every concurrent request: six searches measured 18.5s, versus
        4.1s once FastAPI was allowed to run them in worker threads."""
        from api.main import search
        self.assertFalse(inspect.iscoroutinefunction(search))

    def test_every_blocking_endpoint_stays_synchronous(self):
        from api import main
        for name in ("search", "production_crew", "production_plan",
                     "profile", "similar", "stats"):
            with self.subTest(endpoint=name):
                self.assertFalse(inspect.iscoroutinefunction(getattr(main, name)))


class PoolTests(unittest.TestCase):
    def test_pool_hands_out_distinct_servers(self):
        """A stdio server holds one conversation at a time, so the pool must not
        return the same process to two callers at once."""
        from agent.mcp_clickhouse import _Pool
        pool = _Pool(2)
        with pool.borrow() as first, pool.borrow() as second:
            self.assertIsNot(first, second)

    def test_borrowed_server_returns_to_the_pool(self):
        from agent.mcp_clickhouse import _Pool
        pool = _Pool(1)
        with pool.borrow() as first:
            pass
        with pool.borrow() as again:
            self.assertIs(first, again)


if __name__ == "__main__":
    unittest.main()

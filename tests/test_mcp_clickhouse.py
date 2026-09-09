from __future__ import annotations

import unittest

from agent.mcp_clickhouse import render_query


class MCPQueryRenderingTests(unittest.TestCase):
    def test_renders_typed_values_for_mcp_query_tool(self):
        sql = "SELECT {role:String}, {year:UInt16}, {genres:Array(String)}"
        rendered = render_query(sql, {
            "role": "cinematographer", "year": 2020, "genres": ["Horror", "Crime"]
        })
        self.assertEqual(
            rendered,
            "SELECT 'cinematographer', 2020, ['Horror','Crime']",
        )

    def test_escapes_string_literals(self):
        rendered = render_query("SELECT {value:String}", {"value": "O'Reilly"})
        self.assertEqual(rendered, "SELECT 'O\\'Reilly'")

    def test_missing_parameter_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Missing query parameter"):
            render_query("SELECT {missing:String}", {})


if __name__ == "__main__":
    unittest.main()

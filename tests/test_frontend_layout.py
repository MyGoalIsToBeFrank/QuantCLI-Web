from pathlib import Path
import re
import unittest


class FrontendLayoutTests(unittest.TestCase):
    def test_compact_dashboard_chart_card_keeps_fixed_flex_height(self):
        css = Path('src/frontend/css/style.css').read_text(encoding='utf-8')
        media = re.search(r'@media \(max-width: 1366px\) \{(?P<body>.*?)\n\}', css, re.S)

        self.assertIsNotNone(media)
        self.assertIn('.chart-card', media.group('body'))
        self.assertIn('flex: 0 0 380px;', media.group('body'))
        self.assertIn('height: 380px;', media.group('body'))


if __name__ == '__main__':
    unittest.main()

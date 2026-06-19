import builtins
import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from src.cli import main as cli_main


class _InteractiveStdin:
    def isatty(self):
        return True


class _NonInteractiveStdin:
    def isatty(self):
        return False


class CliInteractiveTests(unittest.TestCase):
    def test_no_args_enters_interactive_loop(self):
        commands = iter(['help', 'exit'])
        output = io.StringIO()

        with patch.object(sys, 'argv', ['QuantCLI.bat']), \
             patch.object(sys, 'stdin', _InteractiveStdin()), \
             patch.object(builtins, 'input', lambda prompt='': next(commands)), \
             redirect_stdout(output):
            cli_main.main()

        out = output.getvalue()
        self.assertIn('QuantCLI 交互模式', out)
        self.assertIn('量化策略 CLI 帮助', out)
        self.assertIn('已退出 QuantCLI', out)

    def test_no_args_without_tty_prints_prompt_once(self):
        output = io.StringIO()

        with patch.object(sys, 'argv', ['QuantCLI.bat']), \
             patch.object(sys, 'stdin', _NonInteractiveStdin()), \
             redirect_stdout(output):
            cli_main.main()

        out = output.getvalue()
        self.assertIn('量化策略 CLI', out)
        self.assertIn('常用命令：', out)
        self.assertNotIn('QuantCLI 交互模式', out)

    def test_data_without_subcommand_prints_data_help(self):
        output = io.StringIO()
        errors = io.StringIO()

        with patch.object(sys, 'argv', ['QuantCLI.bat', 'data']), \
             patch.object(sys, 'stdin', _NonInteractiveStdin()), \
             redirect_stdout(output), \
             redirect_stderr(errors):
            cli_main.main()

        out = output.getvalue()
        self.assertIn('usage: strategy data', out)
        self.assertIn('{list,update,info,verify}', out)
        self.assertEqual('', errors.getvalue())


if __name__ == '__main__':
    unittest.main()

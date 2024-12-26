import unittest
from unittest.mock import patch, MagicMock, call
import socket
import os
import click
from click.testing import CliRunner
import syslog
import pytest

from show.memory_statistics import (
    Config,
    Dict2Obj,
    SonicDBConnector,
    SocketManager,
    format_field_value,
    display_config,
    clean_and_print,
    validate_command,
)


class TestMemoryStatisticsConfig(unittest.TestCase):
    def test_display_config_success(self, mocker):
        """Test successful configuration display"""
        # Mock syslog
        mock_syslog = mocker.patch('syslog.syslog')

        # Mock click.echo
        mock_echo = mocker.patch('click.echo')

        # Create a mock SonicDBConnector
        mock_db_connector = MagicMock()
        mock_db_connector.get_memory_statistics_config.return_value = {
            "enabled": "true",
            "retention_period": "7",
            "sampling_interval": "5"
        }

        # Call the function
        display_config(mock_db_connector)

        # Assert echo calls
        expected_calls = [
            call(f"{'Configuration Field':<30}{'Value'}"),
            call("-" * 50),
            call(f"{'Enabled':<30}True"),
            call(f"{'Retention Time (days)':<30}7"),
            call(f"{'Sampling Interval (minutes)':<30}5")
        ]
        mock_echo.assert_has_calls(expected_calls)
        mock_syslog.assert_not_called()

    def test_display_config_default_values(self, mocker):
        """Test configuration display with default/missing values"""
        # Mock syslog
        mock_syslog = mocker.patch('syslog.syslog')

        # Mock click.echo
        mock_echo = mocker.patch('click.echo')

        # Create a mock SonicDBConnector
        mock_db_connector = MagicMock()
        mock_db_connector.get_memory_statistics_config.return_value = {}

        # Call the function
        display_config(mock_db_connector)

        # Assert echo calls
        expected_calls = [
            call(f"{'Configuration Field':<30}{'Value'}"),
            call("-" * 50),
            call(f"{'Enabled':<30}Not configured"),
            call(f"{'Retention Time (days)':<30}Not configured"),
            call(f"{'Sampling Interval (minutes)':<30}Not configured")
        ]
        mock_echo.assert_has_calls(expected_calls)
        mock_syslog.assert_not_called()

    def test_display_config_exception(self, mocker):
        """Test configuration display when an exception occurs"""
        # Mock syslog
        mock_syslog = mocker.patch('syslog.syslog')

        # Create a mock SonicDBConnector that raises an exception
        mock_db_connector = MagicMock()
        mock_db_connector.get_memory_statistics_config.side_effect = Exception("Database error")

        # Assert that a ClickException is raised
        with pytest.raises(click.ClickException) as context:
            display_config(mock_db_connector)

        # Check the error message and syslog
        assert "Failed to retrieve configuration: Database error" in str(context.value)
        mock_syslog.assert_called_once_with(
            syslog.LOG_ERR,
            "Failed to retrieve configuration: Database error"
        )

    def test_display_config_partial_config(self, mocker):
        """Test configuration display with partial configuration"""
        # Mock syslog
        mock_syslog = mocker.patch('syslog.syslog')

        # Mock click.echo
        mock_echo = mocker.patch('click.echo')

        # Create a mock SonicDBConnector
        mock_db_connector = MagicMock()
        mock_db_connector.get_memory_statistics_config.return_value = {
            "enabled": "false",
            "retention_period": "Unknown"
        }

        # Call the function
        display_config(mock_db_connector)

        # Assert echo calls
        expected_calls = [
            call(f"{'Configuration Field':<30}{'Value'}"),
            call("-" * 50),
            call(f"{'Enabled':<30}False"),
            call(f"{'Retention Time (days)':<30}Not configured"),
            call(f"{'Sampling Interval (minutes)':<30}Not configured")
        ]
        mock_echo.assert_has_calls(expected_calls)
        mock_syslog.assert_not_called()

class TestConfig(unittest.TestCase):
    """Test cases for Config class"""
    def test_default_values(self):
        """Test if Config class has correct default values"""
        self.assertEqual(Config.SOCKET_PATH, '/var/run/dbus/memstats.socket')
        self.assertEqual(Config.SOCKET_TIMEOUT, 30)
        self.assertEqual(Config.BUFFER_SIZE, 8192)
        self.assertEqual(Config.MAX_RETRIES, 3)
        self.assertEqual(Config.RETRY_DELAY, 1.0)
        self.assertEqual(Config.DEFAULT_CONFIG["enabled"], "false")
        self.assertEqual(Config.DEFAULT_CONFIG["retention_period"], "Unknown")
        self.assertEqual(Config.DEFAULT_CONFIG["sampling_interval"], "Unknown")

class TestDict2Obj(unittest.TestCase):
    """Test cases for Dict2Obj class"""
    def test_dict_conversion(self):
        """Test dictionary to object conversion"""
        test_dict = {
            "name": "test",
            "values": [1, 2, 3],
            "nested": {"key": "value"}
        }
        obj = Dict2Obj(test_dict)
        self.assertEqual(obj.name, "test")
        self.assertEqual(obj.values, [1, 2, 3])
        self.assertEqual(obj.nested.key, "value")

    def test_list_conversion(self):
        """Test list conversion"""
        test_list = [{"a": 1}, {"b": 2}]
        obj = Dict2Obj(test_list)
        self.assertEqual(obj.items[0].a, 1)
        self.assertEqual(obj.items[1].b, 2)

    def test_invalid_input(self):
        """Test invalid input handling"""
        with self.assertRaises(ValueError):
            Dict2Obj("invalid")

    def test_to_dict_conversion(self):
        """Test converting object back to dictionary"""
        test_dict = {
            "name": "test",
            "nested": {"key": "value"},
            "list": [{"item": 1}, {"item": 2}]
        }
        obj = Dict2Obj(test_dict)
        result = obj.to_dict()
        self.assertEqual(result, test_dict)

    def test_repr_method(self):
        """Test string representation of Dict2Obj"""
        test_dict = {"name": "test"}
        obj = Dict2Obj(test_dict)
        expected_repr = "<Dict2Obj {'name': 'test'}>"
        self.assertEqual(repr(obj), expected_repr)


class TestSonicDBConnector(unittest.TestCase):
    def setUp(self):
        self.mock_config_db = MagicMock()
        self.patcher = patch('show.memory_statistics.ConfigDBConnector',
                             return_value=self.mock_config_db)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    @patch('show.memory_statistics.ConfigDBConnector')  # Fixed import path
    def test_get_memory_statistics_config(self, mock_config_db):
        """Test retrieving memory statistics configuration"""
        test_config = {
            'memory_statistics': {
                'enabled': 'true',
                'retention_period': '7',
                'sampling_interval': '1'
            }
        }
        mock_config_db.return_value.get_table.return_value = test_config
        connector = SonicDBConnector()
        config = connector.get_memory_statistics_config()
        self.assertEqual(config, test_config['memory_statistics'])

    @patch('show.memory_statistics.ConfigDBConnector')  # Fixed import path
    def test_get_default_config(self, mock_config_db):
        """Test retrieving default configuration when none exists"""
        mock_config_db.return_value.get_table.return_value = {}
        connector = SonicDBConnector()
        config = connector.get_memory_statistics_config()
        self.assertEqual(config, Config.DEFAULT_CONFIG)

    def test_successful_connection(self):
        """Test successful database connection on first attempt"""
        SonicDBConnector()
        self.mock_config_db.connect.assert_called_once()

    def test_connection_retry_success(self):
        """Test successful connection after initial failures"""
        self.mock_config_db.connect.side_effect = [Exception("First try"), Exception("Second try"), None]
        SonicDBConnector()
        self.assertEqual(self.mock_config_db.connect.call_count, 3)

    def test_get_memory_statistics_config_success(self):
        """Test successful retrieval of memory statistics configuration"""
        test_config = {
            'memory_statistics': {
                'enabled': 'true',
                'retention_period': '7',
                'sampling_interval': '1'
            }
        }
        connector = SonicDBConnector()
        self.mock_config_db.get_table.return_value = test_config
        config = connector.get_memory_statistics_config()
        self.assertEqual(config, test_config['memory_statistics'])

    def test_get_memory_statistics_config_empty(self):
        """Test handling of empty configuration"""
        connector = SonicDBConnector()
        self.mock_config_db.get_table.return_value = {}
        config = connector.get_memory_statistics_config()
        self.assertEqual(config, Config.DEFAULT_CONFIG)

    def test_get_memory_statistics_config_error(self):
        """Test error handling in configuration retrieval"""
        connector = SonicDBConnector()
        self.mock_config_db.get_table.side_effect = Exception("Database error")
        with self.assertRaises(RuntimeError) as context:
            connector.get_memory_statistics_config()
        self.assertIn("Error retrieving memory statistics configuration", str(context.exception))


class TestSocketManager(unittest.TestCase):
    """Test cases for SocketManager class"""
    def setUp(self):
        self.socket_path = '/tmp/test_socket'
        self.socket_manager = SocketManager(self.socket_path)

    @patch('socket.socket')
    def test_successful_connection(self, mock_socket):
        """Test successful socket connection"""
        mock_socket.return_value.connect.return_value = None
        self.socket_manager.connect()
        mock_socket.assert_called_with(socket.AF_UNIX, socket.SOCK_STREAM)

    @patch('socket.socket')
    def test_connection_retry(self, mock_socket):
        """Test connection retry mechanism"""
        mock_socket.return_value.connect.side_effect = [
            socket.error("Connection failed"),
            None
        ]
        self.socket_manager.connect()
        self.assertEqual(mock_socket.return_value.connect.call_count, 2)

    @patch('os.path.exists')
    def test_validate_socket_path_success(self, mock_exists):
        """Test successful socket path validation"""
        mock_exists.return_value = True
        self.socket_manager._validate_socket_path()
        mock_exists.assert_called_once_with(os.path.dirname(self.socket_path))

    @patch('socket.socket')
    def test_connect_success(self, mock_socket):
        """Test successful socket connection"""
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock
        self.socket_manager.connect()
        mock_sock.settimeout.assert_called_with(Config.SOCKET_TIMEOUT)
        mock_sock.connect.assert_called_with(self.socket_path)

    @patch('socket.socket')
    def test_connect_retry_success(self, mock_socket):
        """Test successful connection after retries"""
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock
        mock_sock.connect.side_effect = [socket.error(), socket.error(), None]
        self.socket_manager.connect()
        self.assertEqual(mock_sock.connect.call_count, 3)

    @patch('socket.socket')
    def test_receive_all_success(self, mock_socket):
        """Test successful data reception"""
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock
        mock_sock.recv.side_effect = [b'test', b'data', b'']
        self.socket_manager.sock = mock_sock
        result = self.socket_manager.receive_all()
        self.assertEqual(result, 'testdata')

    def test_close_success(self):
        """Test successful socket closure"""
        mock_sock = MagicMock()
        self.socket_manager.sock = mock_sock
        self.socket_manager.close()
        mock_sock.close.assert_called_once()
        self.assertIsNone(self.socket_manager.sock)

    def test_close_with_error(self):
        """Test socket closure with error"""
        mock_sock = MagicMock()
        mock_sock.close.side_effect = Exception("Close error")
        self.socket_manager.sock = mock_sock
        self.socket_manager.close()
        self.assertIsNone(self.socket_manager.sock)

    @patch('socket.socket')
    def test_send_data_success(self, mock_socket):
        """Test successful data sending"""
        mock_sock = MagicMock()
        self.socket_manager.sock = mock_sock
        test_data = "test message"
        self.socket_manager.send(test_data)
        mock_sock.sendall.assert_called_with(test_data.encode('utf-8'))


class TestCLICommands(unittest.TestCase):
    """Test cases for CLI commands"""
    def setUp(self):
        self.runner = CliRunner()
        self.ctx = click.Context(click.Command('test'))

    def test_validate_command_invalid_with_suggestion(self):
        """Test command validation with invalid command but close match"""
        valid_commands = ['show', 'config']
        with self.assertRaises(click.UsageError) as context:
            validate_command('shw', valid_commands)
        self.assertIn("Did you mean 'show'", str(context.exception))

    def test_validate_command_invalid_no_suggestion(self):
        """Test command validation with invalid command and no close match"""
        valid_commands = ['show', 'config']
        with self.assertRaises(click.UsageError) as context:
            validate_command('xyz', valid_commands)
        self.assertIn("Invalid command 'xyz'", str(context.exception))

    def test_format_field_value(self):
        """Test field value formatting"""
        self.assertEqual(format_field_value("enabled", "true"), "True")
        self.assertEqual(format_field_value("enabled", "false"), "False")
        self.assertEqual(format_field_value("retention_period", "Unknown"), "Not configured")
        self.assertEqual(format_field_value("sampling_interval", "5"), "5")

    def test_clean_and_print(self):
        """Test data cleaning and printing"""
        test_data = {
            "data": "Memory Usage: 50%\nSwap Usage: 10%"
        }
        with patch('builtins.print') as mock_print:
            clean_and_print(test_data)
            mock_print.assert_called_with("Memory Statistics:\nMemory Usage: 50%\nSwap Usage: 10%")

    def test_clean_and_print_invalid_data(self):
        """Test clean_and_print with invalid data"""
        with patch('builtins.print') as mock_print:
            clean_and_print("invalid data")
            mock_print.assert_called_with("Error: Invalid data format received")


if __name__ == '__main__':
    unittest.main()

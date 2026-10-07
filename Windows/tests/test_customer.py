"""Customer mode must not inspect credentials already saved on this PC."""
import sys
import unittest
from unittest.mock import patch


@unittest.skipUnless(sys.platform == 'win32', 'Requires Windows desktop')
class CustomerStartupTests(unittest.TestCase):
    def test_customer_startup_never_reads_or_writes_credentials_or_settings(self):
        from bluey import app, project_tracker, tray
        original_init = tray.WindowLifecycle.__init__

        def transient(lifecycle, window, icon, cleanup):
            original_init(lifecycle, window, icon, cleanup)
            window.after(300, lifecycle.quit)

        with patch.object(sys, 'argv', ['bluey', '--customer']), \
             patch('keyring.get_password') as read, \
             patch('keyring.set_password') as write, \
             patch.object(project_tracker, 'settings') as settings, \
             patch.object(project_tracker, 'save_settings') as save, \
             patch.object(tray.WindowLifecycle, '__init__', transient):
            app.main()
            read.assert_not_called()
            write.assert_not_called()
            settings.assert_not_called()
            save.assert_not_called()

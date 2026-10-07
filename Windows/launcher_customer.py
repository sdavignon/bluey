"""Temporary customer client: credentials always belong to the paired phone."""
import sys
from bluey.app import main

if __name__ == '__main__':
    if '--customer' not in sys.argv:
        sys.argv.append('--customer')
    main()

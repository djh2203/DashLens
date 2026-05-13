#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if len(sys.argv) > 1 and sys.argv[1] == 'web':
    from web_panel import main
    main()
else:
    from desktop_manager import DesktopManager
    
    config = None
    config_file = os.path.join(os.path.dirname(__file__), 'config.json')
    if os.path.exists(config_file):
        import json
        with open(config_file) as f:
            config = json.load(f)
    
    manager = DesktopManager(config)
    manager.start()
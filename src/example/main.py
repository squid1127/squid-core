"""Main entry point for the framework."""

from squid_core import Framework

def main():
    """Main function to run the framework."""
    framework = Framework.create()
    framework.run()
    
if __name__ == "__main__":
    main()
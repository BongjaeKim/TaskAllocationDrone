from pyloco.main import main
"""main entry for pyloco command-line interface"""

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()

from org.bccvl.compute import utils
from tempfile import mkdtemp
import os.path
import shutil


def testalgorithm(experiment):
    """
    An algorithm mack function, that generates some test result data.
    """
    # 1. create tempfolder for result files
    tmpdir = mkdtemp()
    try:
        # 2. create some result files
        for fname in ('testfile1.txt', ):
            f = open(os.path.join(tmpdir, fname), 'w')
            f.write(str(range(1, 10)))
            f.close()
        # 3. store results
        utils.store_results(experiment, tmpdir)
    finally:
        # 4. clean up tmpdir
        shutil.rmtree(tmpdir)


def failingtestalgorithm(experiment):
    """
    An algorithm that always fails.
    """
    # 1. create tempfolder for result files
    # 2. create some error files
    pass
    #utils.store_results(experiment, tmpdir)
    # 3. clean up tmpdir

import tempfile
import os.path
from zope.interface import provider
from plone import api
from org.bccvl.site.interfaces import IComputeMethod
from org.bccvl.tasks.celery import app
from org.bccvl.tasks.plone import import_result, import_cleanup, set_progress, after_commit_task


@app.task()
def testjob(params, context):
    """
    An algorithm mock function, that generates some test result data.
    """
    # 1. write file into results_dir
    tmpdir = params['result']['results_dir']
    try:
        # 2. create some result files
        for fname in ('model.RData',
                      'proj_test.tif'):
            f = open(os.path.join(tmpdir, fname), 'w')
            f.write(str(range(1, 10)))
            f.close()
        # 3. store results
        # TODO: tasks called dierctly here; maybe call them as tasks as well? (chain?)
        import_result(params, context)
        import_cleanup(params['result']['results_dir'], context)
        set_progress('COMPLETED', 'Test Task succeeded', context)
    except:
        # 4. clean up if problem otherwise import task cleans up
        #    TODO: should be done by errback or whatever
        import_cleanup(params['result']['results_dir'], context)
        set_progress('FAILED', 'Test Task failed', context)
        raise


@provider(IComputeMethod) # TODO: would expect result as first argument?
def testsdm(result, toolkit):
    # submit test_job into queue
    member = api.user.get_current()
    params = {
        'result': {
            'results_dir': tempfile.mkdtemp(),
            'outputs': {
                'files': {
                    '*.RData': {
                        'title': 'Test SDM Model',
                        'genre': 'DataGenreSDMModel',
                        'mimetype': 'application/x-r-data'
                    },
                    "proj_*.tif": {
                        "title": "Projection to current",
                        "genre": "DataGenreCP",
                        "mimetype": "image/geotiff"
                    },
                }
            }
        },
    }
    context = {
        'context': '/'.join(result.getPhysicalPath()),
        'user': {
            'id': member.getUserName(),
            'email': member.getProperty('email'),
            'fullname': member.getProperty('fullname'),
        },
        'experiment': {
            'title': result.__parent__.title,
            'url': result.__parent__.absolute_url()
        }
    }
    # TODO: create chain with import task?
    # ...  check what happens if task fails (e.g. remove 'experiment' in context)
    after_commit_task(testjob, params, context)


@provider(IComputeMethod) # TODO: would expect result as first argument?
def testprojection(result, toolkit):
    # submit test_job into queue
    member = api.user.get_current()
    params = {
        'result': {
            'results_dir': tempfile.mkdtemp(),
            'outputs': {
                'files': {
                    'proj_*.tif': {
                        'title': 'Future Projection',
                        'genre': 'DataGenreFP',
                        'mimetype': 'image/geotiff',
                    }
                }
            }
        },
    }
    context = {
        'context': '/'.join(result.getPhysicalPath()),
        'user': {
            'id': member.getUserName(),
            'email': member.getProperty('email'),
            'fullname': member.getProperty('fullname'),
        },
        'experiment': {
            'title': result.__parent__.title,
            'url': result.__parent__.absolute_url()
        }
    }
    # TODO: create chain with import task?
    # ...  check what happens if task fails (e.g. remove 'experiment' in context)
    after_commit_task(testjob, params, context)


@provider(IComputeMethod) # TODO: would expect result as first argument?
def testbiodiverse(result, toolkit):
    # submit test_job into queue
    member = api.user.get_current()
    params = {
        'result': {
            'results_dir': tempfile.mkdtemp(),
            'outputs': {
                'files': {
                    'proj_*.tif': {
                        'title': 'Binary Image',
                        'genre': 'DataGenreBinaryImage',
                        'mimetype': 'image/geotiff',
                    }
                }
            }
        },
    }
    context = {
        'context': '/'.join(result.getPhysicalPath()),
        'user': {
            'id': member.getUserName(),
            'email': member.getProperty('email'),
            'fullname': member.getProperty('fullname'),
        },
        'experiment': {
            'title': result.__parent__.title,
            'url': result.__parent__.absolute_url()
        }
    }
    # TODO: create chain with import task?
    # ...  check what happens if task fails (e.g. remove 'experiment' in context)
    after_commit_task(testjob, params, context)

    
@provider(IComputeMethod) # TODO: would expect result as first argument?
def testensemble(result, toolkit):
    # submit test_job into queue
    member = api.user.get_current()
    params = {
        'result': {
            'results_dir': tempfile.mkdtemp(),
            'outputs': {
                'files': {
                    'proj_*.tif': {
                        'title': 'Summary Mean',
                        'genre': 'DataGenreEnsembleResult',
                        'mimetype': 'image/geotiff',
                    }
                }
            }
        },
    }
    context = {
        'context': '/'.join(result.getPhysicalPath()),
        'user': {
            'id': member.getUserName(),
            'email': member.getProperty('email'),
            'fullname': member.getProperty('fullname'),
        },
        'experiment': {
            'title': result.__parent__.title,
            'url': result.__parent__.absolute_url()
        }
    }
    # TODO: create chain with import task?
    # ...  check what happens if task fails (e.g. remove 'experiment' in context)
    after_commit_task(testjob, params, context)


@provider(IComputeMethod) # TODO: would expect result as first argument?
def testtraits(result, toolkit):
    # submit test_job into queue
    member = api.user.get_current()
    params = {
        'result': {
            'results_dir': tempfile.mkdtemp(),
            'outputs': {
                'files': {
                    "*.RData": {
                        "title": "R Species Traits Model object",
                        "genre": "DataGenreSTModel",
                        "mimetype": "application/x-r-data"
                    }
                }
            }
        },
    }
    context = {
        'context': '/'.join(result.getPhysicalPath()),
        'user': {
            'id': member.getUserName(),
            'email': member.getProperty('email'),
            'fullname': member.getProperty('fullname'),
        },
        'experiment': {
            'title': result.__parent__.title,
            'url': result.__parent__.absolute_url()
        }
    }
    # TODO: create chain with import task?
    # ...  check what happens if task fails (e.g. remove 'experiment' in context)
    after_commit_task(testjob, params, context)


@app.task()
def failingtestalgorithm(experiment, request):
    """
    An algorithm that always fails.
    """
    # 1. create tempfolder for result files
    # 2. create some error files
    pass
    #utils.store_results(experiment, tmpdir)
    # 3. clean up tmpdir

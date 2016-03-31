from zope.globalrequest import getRequest
from zope.component.hooks import getSite


def logged_in_handler(event):
    """
    Listen to the event and perform the action accordingly.
    """
    #user = event.object

    # check for came_from or next url ....
    # if empty go to dashboard otherwise to came_from
    request = getRequest()
    if request is None:
        # HTTP request is not present e.g.
        # when doing unit testing / calling scripts from command line
        return

    came_from = request.get('came_from', None)
    site_url = getSite().absolute_url()
    if came_from:
        if came_from.endswith('/'):
            # get rid of trailing slash for comparison
            came_from = came_from.rstrip('/')
        if came_from != site_url:
            # do nothing continue normal login redirect behaviour
            return

    # check if came_from is not empty, then clear it up, otherwise further
    # Plone scripts will override our redirect
    if came_from:
        request['came_from'] = ''
        request.form['came_from'] = ''

    # no redirect set, so go to dashboard
    request.RESPONSE.redirect('{0}/dashboard'.format(site_url))

    #/login_next python script?

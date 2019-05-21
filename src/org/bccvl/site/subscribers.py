from zope.globalrequest import getRequest
from zope.component.hooks import getSite


def logged_in_handler(event):
    """
    Listen to the event and perform the action accordingly.
    """
    request = getRequest()
    if request is None:
        # HTTP request is not present e.g.
        # when doing unit testing / calling scripts from command line
        return

    # Check for came from url for redirecvtion.
    # If empty, then return to gashboard.
    came_from = request.get('came_from', None)
    site_url = getSite().absolute_url()
    if came_from:
        if came_from.rstrip('/') != site_url:
            # return to continue normal login redirect behaviour
            return

        # check if came_from is not empty, then clear it up, otherwise further  
        # Plone scripts will override our redirect
        request['came_from'] = ''
        request.form['came_from'] = ''

    request.RESPONSE.redirect('{0}/dashboard'.format(site_url))

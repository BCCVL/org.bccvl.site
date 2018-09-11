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

    # Go straight to Dashboard regardless of the originating page
    # As part of this, we must clear out the `came_from` parameter as other
    # handlers in the chain may pick up on it and change our redirect
    if request.get('came_from', None):
        request['came_from'] = ''
        request.form['came_from'] = ''

    site_url = getSite().absolute_url()
    request.RESPONSE.redirect('{0}/dashboard'.format(site_url))

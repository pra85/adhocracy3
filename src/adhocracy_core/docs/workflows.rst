Workflows
==========

Preliminaries
-------------

For testing, we need to import some stuff and start the Adhocracy testapp::

    >>> from pprint import pprint
    >>> from adhocracy_core.resources.pool import IBasicPool
    >>> from adhocracy_core.resources.sample_proposal import IProposal
    >>> app_god = getfixture('app_god')
    >>> app_god.base_path = '/adhocracy'

Lets create some content::

    >>> data = {'adhocracy_core.sheets.name.IName': {'name': 'proposals'}}
    >>> resp = app_god.post_resource('/', IBasicPool, data)
    >>> data = {'adhocracy_core.sheets.name.IName': {'name': 'proposal_item'}}
    >>> resp = app_god.post_resource('/proposals', IProposal, data)


Workflows
---------

Workflows are finite state machines assigned to a resource.
States can set the local permissions.
States can have metadata (title, date,...).
State transitions can have a callable to execute arbitrary tasks.

The MetaAPI gives us the states and transitions metadata for each workflow::

    >>> resp_data = app_god.get('/../meta_api').json
    >>> workflow = resp_data['workflows']['sample']

State metadata contains a human readable title::

    >>> state = workflow['states']['draft']
    >>> state['title']
    'Draft'

a description::

    >>> state['description']
    'This phase is for internal review.'

a local ACL (see doc:`authorization`) that is set when entering this state::

    >>> state['acl']
    [['Deny', 'reader', ['view']]]

a hint for the frontend if displaying this state in listing should be restricted::

    >>> state['display_only_to_roles']
    ['manager']

The order these states should be listet is also set, in addition this
defines the initial workflow state (the first in the list)::

    >>> workflow['states_order']
    ['draft', 'announced']

Transition metadata determines the possible state flow and can provide a callable to
execute arbitrary tasks::

     >>> transition = workflow['transitions']['to_announced']
     >>> pprint(transition)
     {'callback': None,
      'from_state': 'draft',
      'permission': 'do_transitions',
      'to_state': 'announced'}


Workflow Assignment
-------------------

Resources have a WorkflowAssignment sheet to assign the wanted workflow::

    >>> resp_data = app_god.get('/proposals/proposal_item').json
    >>> workflow_data = resp_data['data']['adhocracy_core.sheets.workflow.ISample']
    >>> workflow_data['workflow']
    'sample'

and get the current state::

    >>> workflow_data['workflow_state']
    'draft'


in addition we can add custom metadata for specific workflow states::

    >>> workflow_data['announced']['start_date']
    '2015-02-14...
    >>> workflow_data['announced']['description']
    'Soon you can participate...


Workflow transition to states
-----------------------------

We can also modify the state if the workflow has a suitable transition::

    >>> resp_data = app_god.options('/proposals/proposal_item').json
    >>> resp_data['PUT']['request_body']['data']['adhocracy_core.sheets.workflow.ISample']
    {'workflow_state': ['announced']}

NOTE: The available next states depend on the workflow transitions and user permissions.
NOTE: To make this work every state may have only one transition to another state.
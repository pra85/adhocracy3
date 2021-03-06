"""Test rest.views module."""
from unittest.mock import Mock

from pyramid import testing
from pytest import fixture
from pytest import mark
from pytest import raises
import colander
import pytest

from adhocracy_core.interfaces import ISheet
from adhocracy_core.interfaces import IResource
from adhocracy_core.testing import register_sheet


class IResourceX(IResource):
    pass


class ISheetB(ISheet):
    pass


class CountSchema(colander.MappingSchema):

    count = colander.SchemaNode(colander.Int(),
                                default=0,
                                missing=colander.drop)


@fixture
def registry(registry_with_content):
    return registry_with_content


@fixture
def request_(request_, registry, changelog):
    request_.registry = registry
    request_.registry.changelog= changelog
    return request_


@fixture
def mock_authpolicy(registry):
    from pyramid.interfaces import IAuthenticationPolicy
    from adhocracy_core.authentication import TokenHeaderAuthenticationPolicy
    policy = Mock(spec=TokenHeaderAuthenticationPolicy)
    registry.registerUtility(policy, IAuthenticationPolicy)
    return policy


@fixture
def mock_password_sheet(registry, sheet_meta):
    from adhocracy_core.sheets.principal import IPasswordAuthentication
    from adhocracy_core.sheets.principal import PasswordAuthenticationSheet
    sheet = Mock(spec=PasswordAuthenticationSheet)
    sheet.meta = sheet_meta._replace(isheet=IPasswordAuthentication)
    register_sheet(None, sheet, registry)
    return sheet


def make_resource(parent, name, iresource):
        resource = testing.DummyResource(__provides__=iresource,
                                         __parent__=parent,
                                         __name__=name)
        return resource


class TestValidateRequest:

    def call_fut(self, context, request_, **kw):
        from adhocracy_core.rest.views import validate_request_data
        validate_request_data(context, request_, **kw)

    def test_valid_wrong_method_with_data(self, context, request_):
        request_.body = '{"wilddata": "1"}'
        request_.method = 'wrong_method'
        self.call_fut(context, request_)
        assert request_.validated == {}

    def test_valid_no_schema_with_data(self, context, request_):
        request_.body = '{"wilddata": "1"}'
        self.call_fut(context, request_)
        assert request_.validated == {}

    def test_valid_with_schema_no_data(self, context, request_):
        request_.body = ''
        self.call_fut(context, request_, schema=CountSchema())
        assert request_.validated == {}

    def test_valid_with_schema_no_data_empty_dict(self, context, request_):
        request_.body = '{}'
        self.call_fut(context, request_, schema=CountSchema())
        assert request_.validated == {}

    def test_valid_with_schema_no_data_and_defaults(self, context, request_):
        class DefaultDataSchema(colander.MappingSchema):
            count = colander.SchemaNode(colander.Int(),
                                        missing=1)
        request_.body = ''
        self.call_fut(context, request_, schema=DefaultDataSchema())
        assert request_.validated == {'count': 1}

    def test_valid_with_schema_with_data(self, context, request_):
        request_.body = '{"count": "1"}'
        request_.method = 'PUT'
        self.call_fut(context, request_, schema=CountSchema())
        assert request_.validated == {'count': 1}

    def test_valid_with_schema_with_data_in_querystring(self, context,
                                                        request_):
        class QueryStringSchema(colander.MappingSchema):
            count = colander.SchemaNode(colander.Int())
        request_.GET = {'count': 1}
        self.call_fut(context, request_, schema=QueryStringSchema())
        assert request_.validated == {'count': 1}

    def test_valid_with_schema_with_extra_fields_in_querystring_discarded(
            self, context, request_):
        class QueryStringSchema(colander.MappingSchema):
            count = colander.SchemaNode(colander.Int())
        request_.GET = {'count': 1, 'extraflag': 'extra value'}
        self.call_fut(context, request_, schema=QueryStringSchema())
        assert request_.validated == {'count': 1}

    def test_valid_with_schema_with_extra_fields_in_querystring_preserved(
            self, context, request_):

        class PreservingQueryStringSchema(colander.MappingSchema):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.typ.unknown = 'preserve'
            count = colander.SchemaNode(colander.Int())

        request_.GET = {'count': 1, 'extraflag': 'extra value'}
        self.call_fut(context, request_,
                       schema=PreservingQueryStringSchema())
        assert request_.validated == {'count': 1, 'extraflag': 'extra value'}

    def test_valid_multipart_formdata(self, context, request_):
        request_.content_type = 'multipart/form-data'
        request_.method = 'POST'
        request_.POST['count'] = '1'
        self.call_fut(context, request_, schema=CountSchema())
        assert request_.validated == {'count': 1}

    def test_non_valid_with_schema_wrong_data_value(self, context, request_):
        from pyramid.httpexceptions import HTTPBadRequest
        from .exceptions import error_entry
        request_.body = '{"count": "wrong_value"}'
        request_.method = 'POST'
        with pytest.raises(HTTPBadRequest):
            self.call_fut(context, request_, schema=CountSchema())
        assert request_.errors == [error_entry('body',
                                                'count',
                                                '"wrong_value" is not a number')]

    def test_non_valid_with_schema_wrong_data_key_ignore(self, context,
                                                         request_):
        request_.body = '{"wrong_key": "1"}'
        request_.method = 'POST'
        schema = CountSchema().clone()
        schema.typ.unknown = 'ignore'
        self.call_fut(context, request_, schema=schema)
        assert request_.errors == []
        assert request_.validated == {}

    def test_non_valid_with_schema_wrong_data_key_raise(self, context,
                                                        request_):
        from pyramid.httpexceptions import HTTPBadRequest
        from .exceptions import error_entry
        request_.body = '{"wrong_key": "1"}'
        request_.method = 'POST'
        schema = CountSchema().clone()
        schema.typ.unknown = 'raise'
        with pytest.raises(HTTPBadRequest):
            self.call_fut(context, request_, schema=schema)
        assert request_.errors == [error_entry('body',
                                               '',
                                               'Unrecognized keys in mapping: "{\'wrong_key\': \'1\'}"')]

    def test_non_valid_with_non_json_data(self, context, request_):
        from pyramid.httpexceptions import HTTPBadRequest
        from .exceptions import error_entry
        request_.body = b'WRONG'
        request_.method = 'POST'
        with pytest.raises(HTTPBadRequest):
            self.call_fut(context, request_, schema=CountSchema())
        assert request_.errors == [error_entry('body',
                                                None,
                                                'Invalid JSON request body')]

    def test_non_valid_with_schema_wrong_data_cleanup(self, context,
                                                      request_):
        from pyramid.httpexceptions import HTTPBadRequest
        request_.validated = {'secret_data': 'buh'}
        request_.body = '{"count": "wrong_value"}'
        request_.method = 'POST'
        with pytest.raises(HTTPBadRequest):
            self.call_fut(context, request_, schema=CountSchema())
        assert request_.validated == {}

    def test_valid_with_extra_validator(self, context, request_):
        def validator1(context, request_):
            request_.validated = {"validator": "1"}
        self.call_fut(context, request_, extra_validators=[validator1])
        assert request_.validated == {"validator": "1"}

    def test_valid_with_extra_validator_and_wrong_schema_data(self, context,
                                                              request_):
        from pyramid.httpexceptions import HTTPBadRequest
        def validator1(context, request_):
            request_._validator_called = True
        request_.body = '{"count": "wrong"}'
        request_.method = 'POST'
        with pytest.raises(HTTPBadRequest):
            self.call_fut(context, request_, schema=CountSchema(),
                           extra_validators=[validator1])
        assert hasattr(request_, '_validator_called') is False

    def test_valid_with_sequence_schema(self, context, request_):
        class TestListSchema(colander.SequenceSchema):
            elements = colander.SchemaNode(colander.String())

        request_.body = '["alpha", "beta", "gamma"]'
        request_.method = 'POST'
        self.call_fut(context, request_, schema=TestListSchema())
        assert request_.validated == ['alpha', 'beta', 'gamma']

    def test_valid_with_sequence_schema_in_querystring(self, context,
                                                       request_):
        class TestListSchema(colander.SequenceSchema):
            elements = colander.SchemaNode(colander.String())
        self.call_fut(context, request_, schema=TestListSchema())
        # since this doesn't make much sense, the validator is just a no-op
        assert request_.validated == {}

    def test_with_invalid_sequence_schema(self, context, request_):
        class TestListSchema(colander.SequenceSchema):
            elements = colander.SchemaNode(colander.String())
            nonsense_node = colander.SchemaNode(colander.String())

        request_.body = '["alpha", "beta", "gamma"]'
        request_.method = 'POST'
        with pytest.raises(colander.Invalid):
            self.call_fut(context, request_, schema=TestListSchema())
        assert request_.validated == {}

    def test_invalid_with_sequence_schema(self, context, request_):
        class TestListSchema(colander.SequenceSchema):
            elements = colander.SchemaNode(colander.Integer())

        from pyramid.httpexceptions import HTTPBadRequest
        request_.body = '[1, 2, "three"]'
        request_.method = 'POST'
        with pytest.raises(HTTPBadRequest):
            self.call_fut(context, request_, schema=TestListSchema())
        assert request_.validated == {}

    def test_invalid_with_not_sequence_and_not_mapping_schema(self, context,
                                                              request_):
        schema = colander.SchemaNode(colander.Int())
        with pytest.raises(Exception):
            self.call_fut(context, request_, schema=schema)

    def test_valid_user_headers_and_authenticated_user(
            self, context, request_, monkeypatch):
        from unittest.mock import Mock
        from adhocracy_core.rest import views
        request_.headers['X-User-Path'] = 2
        request_.headers['X-User-Token'] = 3
        monkeypatch.setattr(views, 'get_user', Mock(return_value='user'))
        self.call_fut(context, request_)
        assert request_.validated == {}

    def test_invalid_user_headers_but_no_authenticated_user(self, context,
                                                            request_):
        from pyramid.httpexceptions import HTTPBadRequest
        request_.headers['X-User-Path'] = 2
        request_.headers['X-User-Token'] = 3
        with pytest.raises(HTTPBadRequest):
            self.call_fut(context, request_)
        assert request_.validated == {}


class TestValidatePOSTRootVersions:

    def make_one(self, context, request_):
        from adhocracy_core.rest.views import validate_post_root_versions
        validate_post_root_versions(context, request_)

    def test_valid_no_value(self, request_, context):
        self.make_one(context, request_)
        assert request_.errors == []

    def test_valid_empty_value(self, request_, context):
        self.make_one(context, request_)
        request_.validated = {'root_versions': []}
        assert request_.errors == []

    def test_valid_with_value(self, request_, context):
        from adhocracy_core.interfaces import IItemVersion
        from adhocracy_core.interfaces import ISheet
        root = testing.DummyResource(__provides__=(IItemVersion, ISheet))
        request_.validated = {'root_versions': [root]}

        self.make_one(context, request_)

        assert request_.errors == []
        assert request_.validated == {'root_versions': [root]}

    def test_non_valid_value_has_wrong_iface(self, request_, context):
        from adhocracy_core.interfaces import ISheet
        root = testing.DummyResource(__provides__=(IResourceX, ISheet))
        request_.validated = {'root_versions': [root]}

        self.make_one(context, request_)

        assert request_.errors != []
        assert request_.validated == {'root_versions': []}


class TestRespondIfBlocked:

    @fixture
    def mock_reason_if_blocked(self, mocker):
        from . import views
        return mocker.patch.object(views, 'get_reason_if_blocked', autospec=True)

    def call_fut(self, *args):
        from .views import respond_if_blocked
        return respond_if_blocked(*args)

    @mark.parametrize('method,expected', [('OPTIONS', None),
                                          ('DELETE', None),
                                          ('PUT', None),
                                          ])
    def test_ignore_if_method_options_delete_put(self, context, request_,
                                                 method, expected):
        request_.method = method
        assert self.call_fut(context, request_) is expected

    def test_ignore_if_get_reason_is_none(self, context, request_,
                                          mock_reason_if_blocked):
        request_.method = 'GET'
        mock_reason_if_blocked.return_value = None
        assert self.call_fut(context, request_) is None

    def test_raise_if_get_reason(self, context, request_,
                                 mock_reason_if_blocked):
        from pyramid.httpexceptions import HTTPGone
        request_.method = 'GET'
        mock_reason_if_blocked.return_value = 'hidden'
        with raises(HTTPGone):
            self.call_fut(context, request_)


class TestRESTView:

    def make_one(self, context, request):
        from adhocracy_core.rest.views import RESTView
        return RESTView(context, request)

    def test_create(self, request_, context, mocker):
        from . import views
        block_mock = mocker.patch.object(views, 'respond_if_blocked')
        inst = self.make_one(context, request_)
        assert inst.validation_GET == (None, [])
        assert inst.validation_HEAD == (None, [])
        assert inst.validation_OPTIONS == (None, [])
        assert inst.validation_PUT == (None, [])
        assert inst.validation_POST == (None, [])
        assert inst.context is context
        assert inst.request is request_
        assert inst.request.errors == []
        assert inst.request.validated == {}
        assert block_mock.called

    def test_build_updated_resources_dict_empty(self, request_, context):
        inst = self.make_one(context, request_)
        result = inst._build_updated_resources_dict()
        assert result == {}

    def test_build_updated_resources_dict_one_resource(
            self, request_, context, changelog_meta):
        res = testing.DummyResource()
        request_.registry.changelog[res] = changelog_meta._replace(resource=res,
                                                                   created=True)
        inst = self.make_one(context, request_)
        result = inst._build_updated_resources_dict()
        assert result == {'created': [res]}

    def test_build_updated_resources_dict_one_resource_two_events(
            self, request_, context, changelog_meta):
        res = testing.DummyResource()
        request_.registry.changelog[res] = changelog_meta._replace(
            resource=res, created=True, changed_descendants=True)
        inst = self.make_one(context, request_)
        result = inst._build_updated_resources_dict()
        assert result == {'changed_descendants': [res], 'created': [res]}

    def test_build_updated_resources_dict_two_resources(
            self, request_, context, changelog_meta):
        res1 = testing.DummyResource()
        res2 = testing.DummyResource()
        request_.registry.changelog[res1] = \
            changelog_meta._replace(resource=res1, created=True)
        request_.registry.changelog[res2] =\
            changelog_meta._replace(resource=res2, created=True)
        inst = self.make_one(context, request_)
        result = inst._build_updated_resources_dict()
        assert list(result.keys()) == ['created']
        assert set(result['created']) == {res1, res2}


class TestResourceRESTView:

    def make_one(self, context, request_):
        from adhocracy_core.rest.views import ResourceRESTView
        return ResourceRESTView(context, request_)

    def test_create(self, request_, context):
        from adhocracy_core.rest.views import RESTView
        inst = self.make_one(context, request_)
        assert isinstance(inst, RESTView)
        assert inst.content is request_.registry.content

    def test_options_with_sheets_and_addables(
            self, request_, context, resource_meta, mock_sheet):
        content = request_.registry.content
        content.get_sheets_edit.return_value = [mock_sheet]
        content.get_sheets_read.return_value = [mock_sheet]
        content.get_resources_meta_addable.return_value = [resource_meta]
        content.get_sheets_create.return_value = [mock_sheet]
        inst = self.make_one(context, request_)

        response = inst.options()

        wanted = \
        {'GET': {'request_body': {},
         'request_querystring': {},
         'response_body': {'content_type': '',
                           'data': {ISheet.__identifier__: {}},
                           'path': ''}},
         'HEAD': {},
         'OPTIONS': {},
         'POST': {'request_body': [{'content_type': IResource.__identifier__,
                                    'data': {ISheet.__identifier__: {}}}],
                  'response_body': {'content_type': '', 'path': ''}},
         'PUT': {'request_body': {'content_type': '',
                                  'data': {ISheet.__identifier__: {}}},
                 'response_body': {'content_type': '', 'path': ''}}}
        assert wanted['GET'] == response['GET']
        assert wanted['POST'] == response['POST']
        assert wanted['PUT'] == response['PUT']
        assert wanted['HEAD'] == response['HEAD']
        assert wanted['OPTIONS'] == response['OPTIONS']

    def test_options_with_sheets_and_addables_but_no_permissons(
            self, config, request_, context, resource_meta, mock_sheet):
        content = request_.registry.content
        content.get_sheets_edit.return_value = [mock_sheet]
        content.get_sheets_read.return_value = [mock_sheet]
        content.get_resources_meta_addable.return_value = [resource_meta]
        content.get_sheets_create.return_value = [mock_sheet]
        inst = self.make_one(context, request_)
        config.testing_securitypolicy(userid='hank', permissive=False)

        response = inst.options()

        wanted = {'HEAD': {},
                  'OPTIONS': {}}
        assert wanted == response

    def test_options_without_sheets_and_addables(self, request_, context):
        inst = self.make_one(context, request_)
        response = inst.options()
        wanted = {'HEAD': {},
                  'OPTIONS': {}}
        assert wanted == response

    def test_add_metadata_permissions_info_no_metadata(self, request_, context):
        inst = self.make_one(context, request_)
        d = {'DummySheet': {}}
        inst._add_metadata_edit_permission_info(d)
        assert d == {'DummySheet': {}}

    def test_add_metadata_permissions_info_without_hide_permission(
            self, request_, context):
        from adhocracy_core.sheets.metadata import IMetadata
        request_.has_permission = Mock(return_value=False)
        inst = self.make_one(context, request_)
        d = {IMetadata.__identifier__: {}}
        inst._add_metadata_edit_permission_info(d)
        assert d == {IMetadata.__identifier__: {'deleted': [True, False]}}

    def test_add_metadata_permissions_info_with_hide_permission(
            self, request_, context):
        from adhocracy_core.sheets.metadata import IMetadata
        request_.has_permission = Mock(return_value=True)
        inst = self.make_one(context, request_)
        d = {IMetadata.__identifier__: {}}
        inst._add_metadata_edit_permission_info(d)
        assert d == {IMetadata.__identifier__: {'deleted': [True, False],
                                                'hidden': [True, False]}}

    def test_add_workflow_permissions_info(
            self, request_, context, mock_sheet, mock_workflow):
        from adhocracy_core.sheets.workflow import IWorkflowAssignment
        mock_workflow.get_next_states.return_value = ['draft']
        mock_sheet.get.return_value = {'workflow': mock_workflow}
        mock_sheet.meta = mock_sheet.meta._replace(isheet=IWorkflowAssignment)
        editable_sheets = [mock_sheet]
        inst = self.make_one(context, request_)
        d = {}
        inst._add_workflow_edit_permission_info(d, editable_sheets)
        assert d ==\
            {IWorkflowAssignment.__identifier__: {'workflow_state': ['draft']}}

    def test_add_workflow_permissions_info_without_workflow(
           self, request_, context, mock_sheet):
        from adhocracy_core.sheets.workflow import IWorkflowAssignment
        mock_sheet.get.return_value = {'workflow': None}
        mock_sheet.meta = mock_sheet.meta._replace(isheet=IWorkflowAssignment)
        editable_sheets = [mock_sheet]
        inst = self.make_one(context, request_)
        d = {}
        inst._add_workflow_edit_permission_info(d, editable_sheets)
        assert d ==\
            {IWorkflowAssignment.__identifier__: {'workflow_state': []}}

    def test_get_no_sheets(self, request_, context):
        from adhocracy_core.rest.schemas import GETResourceResponseSchema

        inst = self.make_one(context, request_)
        response = inst.get()

        wanted = GETResourceResponseSchema().serialize()
        wanted['path'] = request_.application_url + '/'
        wanted['data'] = {}
        wanted['content_type'] = IResource.__identifier__
        assert wanted == response

    def test_get_with_sheets(self, request_, context, mock_sheet):
        mock_sheet.get_cstruct.return_value = {'name': '1'}
        mock_sheet.schema.add(colander.SchemaNode(colander.Int(), name='name'))
        request_.registry.content.get_sheets_read.return_value = [mock_sheet]
        inst = self.make_one(context, request_)
        assert inst.get()['data'][ISheet.__identifier__] == {'name': '1'}


class TestSimpleRESTView:

    def make_one(self, context, request):
        from adhocracy_core.rest.views import SimpleRESTView
        return SimpleRESTView(context, request)

    def test_create(self, context, request_):
        from adhocracy_core.rest.views import ResourceRESTView
        from adhocracy_core.rest.schemas import PUTResourceRequestSchema
        inst = self.make_one(context, request_)
        assert issubclass(inst.__class__, ResourceRESTView)
        assert inst.validation_PUT == (PUTResourceRequestSchema, [])
        assert 'options' in dir(inst)
        assert 'get' in dir(inst)
        assert 'put' in dir(inst)

    def test_put_no_sheets(self, request_, context, mock_sheet):
        request_.registry.content.get_sheets_edit.return_value = [mock_sheet]
        request_.validated = {"content_type": "X", "data": {}}

        inst = self.make_one(context, request_)
        response = inst.put()

        wanted = {'path': request_.application_url + '/',
                  'content_type': IResource.__identifier__,
                  'updated_resources': {'changed_descendants': [],
                          'created': [],
                          'modified': [],
                          'removed': []}}
        assert wanted == response

    def test_put_with_sheets(self, request_, context, mock_sheet):
        request_.registry.content.get_sheets_edit.return_value = [mock_sheet]
        data = {'content_type': 'X',
                'data': {ISheet.__identifier__: {'x': 'y'}}}
        request_.validated = data

        inst = self.make_one(context, request_)
        response = inst.put()
        assert mock_sheet.set.call_args[0][0] == {'x': 'y'}


class TestPoolRESTView:

    def make_one(self, context, request_):
        from adhocracy_core.rest.views import PoolRESTView
        return PoolRESTView(context, request_)

    def test_create(self, request_, context):
        from adhocracy_core.rest.views import SimpleRESTView
        from adhocracy_core.rest.schemas import POSTResourceRequestSchema
        inst = self.make_one(context, request_)
        assert issubclass(inst.__class__, SimpleRESTView)
        assert inst.validation_POST == (POSTResourceRequestSchema, [])
        assert 'options' in dir(inst)
        assert 'get' in dir(inst)
        assert 'put' in dir(inst)

    def test_get_no_sheets(self, request_, context):
        from adhocracy_core.rest.schemas import GETResourceResponseSchema

        inst = self.make_one(context, request_)
        response = inst.get()

        wanted = GETResourceResponseSchema().serialize()
        wanted['path'] = request_.application_url + '/'
        wanted['data'] = {}
        wanted['content_type'] = IResource.__identifier__
        assert wanted == response

    def test_get_pool_sheet_with_query_params(self, request_, context,
                                                    mock_sheet):
        from adhocracy_core.sheets.pool import IPool
        mock_sheet.meta = mock_sheet.meta._replace(isheet=IPool)
        mock_sheet.get_cstruct.return_value = {}
        request_.registry.content.get_sheets_read.return_value = [mock_sheet]
        request_.validated['param1'] = 1

        inst = self.make_one(context, request_)
        response = inst.get()

        assert response['data'] == {IPool.__identifier__: {}}
        assert mock_sheet.get_cstruct.call_args[1] == {'params': {'param1': 1,
                                                       'depth': 1,
                                                       'root': context,
                                                       }}

    def test_post(self, request_, context):
        request_.root = context
        child = make_resource(context, 'child', IResourceX)
        request_.registry.content.create.return_value = child
        request_.validated = {'content_type': IResourceX, 'data': {}}
        inst = self.make_one(context, request_)
        inst._get_post_metric_name = Mock()
        response = inst.post()

        wanted = {'path': request_.application_url + '/child/',
                  'content_type': IResourceX.__identifier__,
                  'updated_resources': {'changed_descendants': [],
                                        'created': [],
                                        'modified': [],
                                        'removed': []}}
        assert inst._get_post_metric_name.called
        assert wanted == response

    def test_get_post_metric_name(self, context, request_):
        request_.validated['content_type'] = IResourceX
        inst = self.make_one(context, request_)
        assert inst._get_post_metric_name() == 'process.post'

    def test_get_post_metric_name_proposalversion(self, context, request_):
        from adhocracy_core.resources.proposal import IProposalVersion
        request_.validated['content_type'] = IProposalVersion
        inst = self.make_one(context, request_)
        assert inst._get_post_metric_name() == 'process.post.proposalversion'

    def test_get_post_metric_name_rateversion(self, context, request_):
        from adhocracy_core.resources.rate import IRateVersion
        request_.validated['content_type'] = IRateVersion
        inst = self.make_one(context, request_)
        assert inst._get_post_metric_name() == 'process.post.rateversion'

    def test_put_no_sheets(self, request_, context, mock_sheet):
        request_.registry.content.get_sheets_edit.return_value = [mock_sheet]
        request_.validated = {"content_type": "X", "data": {}}
        inst = self.make_one(context, request_)
        response = inst.put()
        wanted = {'path': request_.application_url + '/',
                  'content_type': IResource.__identifier__,
                  'updated_resources': {'changed_descendants': [],
                                        'created': [],
                                        'modified': [],
                                        'removed': []}}
        assert wanted == response


class TestUsersRESTView:

    def make_one(self, context, request_):
        from adhocracy_core.rest.views import UsersRESTView
        return UsersRESTView(context, request_)

    def test_create(self, request_, context):
        from adhocracy_core.rest.views import PoolRESTView
        inst = self.make_one(context, request_)
        assert issubclass(inst.__class__, PoolRESTView)
        assert 'options' in dir(inst)
        assert 'get' in dir(inst)
        assert 'put' in dir(inst)

    def test_post(self, request_, context):
        child = make_resource(context, 'child', IResourceX)
        request_.registry.content.create.return_value = child
        request_.validated = {'content_type': IResourceX,
                              'data': {}}
        inst = self.make_one(context, request_)
        response = inst.post()

        wanted = {'path': request_.application_url + '/child/',
                  'content_type': IResourceX.__identifier__,
                  'updated_resources': {'changed_descendants': [],
                                        'created': [],
                                        'modified': [],
                                        'removed': []}}
        request_.registry.content.create.assert_called_with(
                IResourceX.__identifier__,
                parent=context,
                creator=None,
                appstructs={},
                root_versions=[],
                request=request_,
                is_batchmode=False,
        )
        assert wanted == response


class TestItemRESTView:

    @fixture
    def mock_tags_sheet(self, registry, mock_sheet):
        registry.content.get_sheet.return_value = mock_sheet
        return mock_sheet

    def make_one(self, context, request_):
        from adhocracy_core.rest.views import ItemRESTView
        return ItemRESTView(context, request_)

    def test_create(self, request_, context):
        from adhocracy_core.rest.views import validate_post_root_versions
        from adhocracy_core.rest.views import SimpleRESTView
        from adhocracy_core.rest.schemas import POSTItemRequestSchema
        inst = self.make_one(context, request_)
        assert issubclass(inst.__class__, SimpleRESTView)
        assert inst.validation_POST == (POSTItemRequestSchema,
                                        [validate_post_root_versions])
        assert 'options' in dir(inst)
        assert 'get' in dir(inst)
        assert 'put' in dir(inst)

    def test_get_item_with_first_version(self, request_, item,
                                         mock_tags_sheet):
        from adhocracy_core.interfaces import IItem
        item['version0'] = testing.DummyResource()
        mock_tags_sheet.get.return_value = {'FIRST': item['version0']}
        inst = self.make_one(item, request_)

        wanted = {'path': request_.application_url + '/',  'data': {},
                  'content_type': IItem.__identifier__,
                  'first_version_path': request_.application_url + '/version0/'}
        assert inst.get() == wanted

    def test_get_item_without_first_version(self, request_, item,
                                            mock_tags_sheet):
        from adhocracy_core.interfaces import IItem
        mock_tags_sheet.get.return_value = {'FIRST': None}
        inst = self.make_one(item, request_)

        wanted = {'path': request_.application_url + '/',  'data': {},
                  'content_type': IItem.__identifier__,
                  'first_version_path': None}
        assert inst.get() == wanted

    def test_post(self, request_, context):
        from adhocracy_core.utils import set_batchmode
        set_batchmode(request_, True)
        child = make_resource(context, 'child', IResourceX)
        request_.registry.content.create.return_value = child
        request_.validated = {'content_type': IResourceX,
                              'data': {}}
        inst = self.make_one(context, request_)
        response = inst.post()

        wanted = {'path': request_.application_url + '/child/',
                  'content_type': IResourceX.__identifier__,
                  'updated_resources': {'changed_descendants': [],
                                        'created': [],
                                        'modified': [],
                                        'removed': []}}
        request_.registry.content.create.assert_called_with(
                IResourceX.__identifier__,
                parent=context,
                creator=None,
                appstructs={},
                root_versions=[],
                request=request_,
                is_batchmode=True)
        assert wanted == response

    def test_post_item(self, request_, context, mock_tags_sheet):
        from adhocracy_core.interfaces import IItem
        from adhocracy_core.interfaces import IItemVersion
        child = make_resource(context, 'child', IItem)
        child['version0'] = testing.DummyResource()
        request_.registry.content.create.return_value = child
        request_.validated = {'content_type': IItemVersion,
                              'data': {}}
        mock_tags_sheet.get.return_value = {'FIRST': child['version0']}
        inst = self.make_one(context, request_)
        response = inst.post()

        first_version_path = request_.application_url + '/child/version0/'
        assert response['path'] == request_.application_url + '/child/'
        assert response['first_version_path'] == first_version_path

    def test_post_itemversion(self, request_, context):
        from adhocracy_core.interfaces import IItemVersion
        child = make_resource(context, 'child', IItemVersion)
        request_.registry.content.create.return_value = child
        root = testing.DummyResource(__provides__=IItemVersion)
        request_.validated = {'content_type': IItemVersion,
                              'data': {},
                              'root_versions': [root]}
        inst = self.make_one(context, request_)
        response = inst.post()
        assert response['path'] == request_.application_url + '/child/'
        assert request_.registry.content \
            .create.call_args[1]['root_versions'] == [root]

    def test_post_itemversion_batchmode_no_last_version_in_transaction(
            self, request_, context, mock_tags_sheet):
        from adhocracy_core.interfaces import IItemVersion
        from adhocracy_core.utils import set_batchmode
        child = make_resource(context, 'child', IItemVersion)
        mock_tags_sheet.get.return_value = {'LAST': child,
                                            'FIRST': None}
        request_.registry.content.create.return_value = child
        request_.validated = {'content_type': IItemVersion,
                              'data': {}}
        request_.registry.content.get_sheet.return_value = mock_tags_sheet
        set_batchmode(request_, True)
        inst = self.make_one(context, request_)
        response = inst.post()
        assert response['path'] == request_.application_url + '/child/'

    def test_valid_itemversion_batchmode_last_version_in_transaction(
            self, request_, context, mock_sheet, changelog_meta):
        from copy import deepcopy
        from adhocracy_core.interfaces import IItemVersion
        from adhocracy_core.utils import set_batchmode
        child = make_resource(context, 'last_version', IItemVersion)
        mock_tags_sheet = deepcopy(mock_sheet)
        mock_tags_sheet.get.return_value = {'LAST': child,
                                            'FIRST': None}
        set_batchmode(request_, True)
        request_.root = context
        request_.validated = {'content_type': IItemVersion,
                              'data': {ISheet.__identifier__: {'x': 'y'}},
                              'root_versions': []}
        mock_versions_sheet = deepcopy(mock_sheet)
        mock_other_sheet = deepcopy(mock_sheet)
        mock_other_sheet.get.return_value = {'x': 'y'}
        request_.registry.content.get_sheet.side_effect = [mock_tags_sheet,
                                                           mock_tags_sheet,
                                                           mock_other_sheet]
        request_.registry.changelog['/last_version'] =\
            changelog_meta._replace(created=True)
        request_.registry.content.get_sheets_create.return_value =\
            [mock_versions_sheet,
             mock_other_sheet]
        inst = self.make_one(context, request_)
        response = inst.post()

        mock_other_sheet.set.assert_called_with({'x': 'y'}, request=request_)
        assert response['path'] == request_.application_url + '/last_version/'

    def test_post_itemversion_batchmode_first_and_last_version_in_transaction(
            self, request_, context, mock_sheet, changelog_meta, sheet_meta):
        from copy import deepcopy
        from adhocracy_core.interfaces import IItemVersion
        from adhocracy_core.sheets.versions import IVersionable
        from adhocracy_core.utils import set_batchmode
        child = make_resource(context, 'last_version', IItemVersion)
        mock_tags_sheet = deepcopy(mock_sheet)
        mock_tags_sheet.get.return_value = {'LAST': child,
                                            'FIRST': child}
        set_batchmode(request_, True)
        request_.root = context
        request_.validated = {'content_type': IItemVersion,
                              'data': {ISheet.__identifier__: {'x': 'y'}},
                              'root_versions': []}
        mock_versions_sheet = deepcopy(mock_sheet)
        mock_versions_sheet.meta = sheet_meta._replace(isheet=IVersionable)
        mock_other_sheet = deepcopy(mock_sheet)
        mock_other_sheet.get.return_value = {'x': 'y'}
        request_.registry.content.get_sheet.side_effect = [mock_tags_sheet,
                                                           mock_tags_sheet,
                                                           mock_other_sheet]
        request_.registry.changelog['/last_version'] =\
            changelog_meta._replace(created=True)
        request_.registry.content.get_sheets_create.return_value = \
            [mock_versions_sheet,
             mock_other_sheet]
        inst = self.make_one(context, request_)
        response = inst.post()

        mock_other_sheet.set.assert_called_with({'x': 'y'}, request=request_)
        assert response['path'] == request_.application_url + '/last_version/'

    def test_put_no_sheets(self, request_, context, mock_sheet):
        request_.registry.content.get_sheets_edit.return_value = [mock_sheet]
        request_.validated = {"content_type": "X", "data": {}}
        inst = self.make_one(context, request_)
        response = inst.put()
        wanted = {'path': request_.application_url + '/',
                  'content_type': IResource.__identifier__,
                  'updated_resources': {'changed_descendants': [],
                                        'created': [],
                                        'modified': [],
                                        'removed': []}}
        assert wanted == response


class TestBadgeAssignmentsRESTView:

    @fixture
    def assignment_sheet(self, mock_sheet):
        from copy import deepcopy
        from adhocracy_core.sheets.badge import IBadgeAssignment
        sheet = deepcopy(mock_sheet)
        sheet.meta = sheet.meta._replace(isheet=IBadgeAssignment)
        return sheet

    @fixture
    def mock_get_assignables(self, monkeypatch):
        from adhocracy_core.rest import views
        mock = Mock(spec=views.get_assignable_badges)
        monkeypatch.setattr(views, 'get_assignable_badges', mock)
        return mock

    def make_one(self, context, request_):
        from adhocracy_core.rest.views import BadgeAssignmentsRESTView
        return BadgeAssignmentsRESTView(context, request_)

    def test_create(self, context, request_):
        from adhocracy_core.rest.views import PoolRESTView
        inst = self.make_one(context, request_)
        assert isinstance(inst, PoolRESTView)

    def test_get(self, context, request_):
        inst = self.make_one(context, request_)
        response = inst.get()
        assert response == {'content_type': 'adhocracy_core.interfaces.IResource',
                            'data': {},
                            'path': 'http://example.com/'}

    def test_options_ignore_if_no_postable_resources(self, context, request_):
        inst = self.make_one(context, request_)
        response = inst.options()
        assert response == {'HEAD': {}, 'OPTIONS': {}}

    def test_options_ignore_if_no_postable_assignments_sheets(
            self, request_, context, resource_meta,  mock_sheet):
        registry = request_.registry.content
        registry.get_resources_meta_addable.return_value = [resource_meta]
        registry.get_sheets_create.return_value = [mock_sheet]
        inst = self.make_one(context, request_)
        response = inst.options()
        assert response['POST']['request_body'][0]['data'] ==\
            {'adhocracy_core.interfaces.ISheet': {}}

    def test_options_add_assignable_badges(
            self, request_, context, resource_meta, assignment_sheet,
            mock_get_assignables):
        registry = request_.registry.content
        registry.get_resources_meta_addable.return_value = [resource_meta]
        registry.get_sheets_create.return_value = [assignment_sheet]
        badge = testing.DummyResource()
        mock_get_assignables.return_value = [badge]
        inst = self.make_one(context, request_)
        response = inst.options()
        assert response['POST']['request_body'][0]['data'] ==\
            {'adhocracy_core.sheets.badge.IBadgeAssignment':
                 {'badge': ['http://example.com/']}}

    def test_post_valid(self, request_, context):
        request = request_
        request.root = context
        child = testing.DummyResource(__provides__=IResourceX)
        child.__parent__ = context
        child.__name__ = 'child'
        request.registry.content.create.return_value = child
        request.validated = {'content_type': IResourceX, 'data': {}}
        inst = self.make_one(context, request_)
        response = inst.post()
        wanted = {'path': request.application_url + '/child/',
                  'content_type': IResourceX.__identifier__,
                  'updated_resources': {'changed_descendants': [],
                                        'created': [],
                                        'modified': [],
                                        'removed': []}}
        assert wanted == response


class TestMetaApiView:

    def make_one(self, request_, context):
        from adhocracy_core.rest.views import MetaApiView
        return MetaApiView(context, request_)

    def test_get_empty(self, request_, context):
        inst = self.make_one(request_, context)
        response = inst.get()
        assert response['resources'] == {}
        assert response['sheets'] == {}
        assert response['workflows'] == {}

    def test_get_resources(self, request_, context, resource_meta):
        request_.registry.content.resources_meta[IResource] = resource_meta
        inst = self.make_one(request_, context)
        resp = inst.get()
        assert IResource.__identifier__ in resp['resources']
        assert resp['resources'][IResource.__identifier__]['sheets'] == []
        assert resp['resources'][IResource.__identifier__]['super_types'] == []

    def test_get_resources_with_super_types(self, request_, context, resource_meta):
        class IResourceBX(IResourceX):
            pass
        resource_meta._replace(iresource=IResourceBX)
        request_.registry.content.resources_meta[IResourceBX] = resource_meta
        inst = self.make_one(request_, context)
        resp = inst.get()
        assert resp['resources'][IResourceBX.__identifier__]['super_types'] ==\
            [IResourceX.__identifier__]

    def test_get_resources_with_sheets_meta(self, request_, context, resource_meta):
        resource_meta = resource_meta._replace(basic_sheets=(ISheet,),
                                               extended_sheets=(ISheetB,))
        request_.registry.content.resources_meta[IResource] = resource_meta
        inst = self.make_one(request_, context)

        resp = inst.get()['resources']

        wanted_sheets = [ISheet.__identifier__, ISheetB.__identifier__]
        assert wanted_sheets == resp[IResource.__identifier__]['sheets']

    def test_get_resources_with_element_types_metadata(self, request_, context, resource_meta):
        resource_meta = resource_meta._replace(element_types=[IResource,
                                                              IResourceX])
        request_.registry.content.resources_meta[IResource] = resource_meta
        inst = self.make_one(request_, context)

        resp = inst.get()['resources']

        wanted = [IResource.__identifier__, IResourceX.__identifier__]
        assert wanted == resp[IResource.__identifier__]['element_types']

    def test_get_resources_with_item_type_metadata(self, request_, context, resource_meta):
        resource_meta = resource_meta._replace(item_type=IResourceX)
        request_.registry.content.resources_meta[IResource] = resource_meta
        inst = self.make_one(request_, context)

        resp = inst.get()['resources']

        wanted = IResourceX.__identifier__
        assert wanted == resp[IResource.__identifier__]['item_type']

    def test_get_sheets(self, request_, context, sheet_meta):
        request_.registry.content.sheets_meta[ISheet] = sheet_meta
        inst = self.make_one(request_, context)
        response = inst.get()
        assert ISheet.__identifier__ in response['sheets']
        assert 'fields' in response['sheets'][ISheet.__identifier__]
        assert response['sheets'][ISheet.__identifier__]['fields'] == []
        assert response['sheets'][ISheet.__identifier__]['super_types'] == []

    def test_get_sheets_with_super_types(self, request_, context, sheet_meta):
        class ISheetBX(ISheetB):
            pass
        sheet_meta = sheet_meta._replace(isheet=ISheetBX)
        request_.registry.content.sheets_meta[ISheetBX] = sheet_meta
        inst = self.make_one(request_, context)
        response = inst.get()['sheets'][ISheetBX.__identifier__]
        assert response['super_types'] == [ISheetB.__identifier__]

    def test_get_sheets_with_field(self, request_, context, sheet_meta):
        class SchemaF(colander.MappingSchema):
            test = colander.SchemaNode(colander.Int())
        sheet_meta = sheet_meta._replace(schema_class=SchemaF)
        request_.registry.content.sheets_meta[ISheet] = sheet_meta
        inst = self.make_one(request_, context)

        response = inst.get()['sheets'][ISheet.__identifier__]

        assert len(response['fields']) == 1
        field_metadata = response['fields'][0]
        assert field_metadata['create_mandatory'] is False
        assert field_metadata['readable'] is True
        assert field_metadata['editable'] is True
        assert field_metadata['creatable'] is True
        assert field_metadata['name'] == 'test'
        assert 'valuetype' in field_metadata

    def test_get_sheet_with_readonly_field(self, request_, context, sheet_meta):
        class SchemaF(colander.MappingSchema):
            test = colander.SchemaNode(colander.Int(), readonly=True)
        sheet_meta = sheet_meta._replace(schema_class=SchemaF)
        request_.registry.content.sheets_meta[ISheet] = sheet_meta
        inst = self.make_one(request_, context)

        response = inst.get()['sheets'][ISheet.__identifier__]

        field_metadata = response['fields'][0]
        assert field_metadata['editable'] is False
        assert field_metadata['creatable'] is False
        assert field_metadata['create_mandatory'] is False

    def test_get_sheets_with_field_colander_noniteratable(self, request_, context, sheet_meta):
        class SchemaF(colander.MappingSchema):
            test = colander.SchemaNode(colander.Int())
        sheet_meta = sheet_meta._replace(schema_class=SchemaF)
        request_.registry.content.sheets_meta[ISheet] = sheet_meta
        inst = self.make_one(request_, context)

        response = inst.get()['sheets'][ISheet.__identifier__]

        field_metadata = response['fields'][0]
        assert 'containertype' not in field_metadata
        assert field_metadata['valuetype'] == 'Integer'

    def test_get_sheets_with_field_adhocracy_noniteratable(self, request_, context, sheet_meta):
        from adhocracy_core.schema import Name
        class SchemaF(colander.MappingSchema):
            test = colander.SchemaNode(Name())
        sheet_meta = sheet_meta._replace(schema_class=SchemaF)
        request_.registry.content.sheets_meta[ISheet] = sheet_meta
        inst = self.make_one(request_, context)

        response = inst.get()['sheets'][ISheet.__identifier__]

        field_metadata = response['fields'][0]
        assert 'containertype' not in field_metadata
        assert field_metadata['valuetype'] == 'adhocracy_core.schema.Name'

    def test_get_sheets_with_field_adhocracy_referencelist(self, request_, context, sheet_meta):
        from adhocracy_core.interfaces import SheetToSheet
        from adhocracy_core.schema import UniqueReferences
        class SchemaF(colander.MappingSchema):
            test = UniqueReferences(reftype=SheetToSheet)
        sheet_meta = sheet_meta._replace(schema_class=SchemaF)
        request_.registry.content.sheets_meta[ISheet] = sheet_meta
        inst = self.make_one(request_, context)

        sheet_metadata = inst.get()['sheets'][ISheet.__identifier__]

        field_metadata = sheet_metadata['fields'][0]
        assert field_metadata['containertype'] == 'list'
        assert field_metadata['valuetype'] == 'adhocracy_core.schema.AbsolutePath'
        assert field_metadata['targetsheet'] == ISheet.__identifier__

    def test_get_sheets_with_field_adhocracy_back_referencelist(self, request_, context, sheet_meta):
        from adhocracy_core.interfaces import SheetToSheet
        from adhocracy_core.schema import UniqueReferences
        class BSheetToSheet(SheetToSheet):
            pass
        BSheetToSheet.setTaggedValue('source_isheet', ISheetB)
        class SchemaF(colander.MappingSchema):
            test = UniqueReferences(reftype=BSheetToSheet, backref=True)
        sheet_meta = sheet_meta._replace(schema_class=SchemaF)
        request_.registry.content.sheets_meta[ISheet] = sheet_meta
        inst = self.make_one(request_, context)

        sheet_metadata = inst.get()['sheets'][ISheet.__identifier__]

        field_metadata = sheet_metadata['fields'][0]
        assert field_metadata['targetsheet'] == ISheetB.__identifier__

    def test_get_sheets_with_field_non_generic_or_container(
            self, request_, context, sheet_meta):
        from adhocracy_core.schema import Identifier
        class SchemaF(colander.MappingSchema):
            id = Identifier()
        sheet_meta = sheet_meta._replace(schema_class=SchemaF)
        request_.registry.content.sheets_meta[ISheet] = sheet_meta
        inst = self.make_one(request_, context)
        sheet_metadata = inst.get()['sheets'][ISheet.__identifier__]
        field_metadata = sheet_metadata['fields'][0]
        assert field_metadata['valuetype'] == 'adhocracy_core.schema.Identifier'

    def test_get_sheets_with_sequence_schema_as_node(self, request_, context,
                                                     sheet_meta):
        from adhocracy_core.schema import Roles
        class SchemaF(colander.MappingSchema):
            roles = Roles()
        sheet_meta = sheet_meta._replace(schema_class=SchemaF)
        request_.registry.content.sheets_meta[ISheet] = sheet_meta
        inst = self.make_one(request_, context)
        sheet_metadata = inst.get()['sheets'][ISheet.__identifier__]
        field_metadata = sheet_metadata['fields'][0]
        assert field_metadata['valuetype'] == 'adhocracy_core.schema.Role'
        assert field_metadata['containertype'] == 'list'

    # TODO test for single reference

    def test_get_workflows(self, request_, context):
        inst = self.make_one(request_, context)
        request_.registry.content.workflows_meta['sample'] = {'states': {},
                                                             'transitions': {}}
        workflows_meta = inst.get()['workflows']
        assert workflows_meta == {'sample': {'initial_state': '',
                                             'states': {},
                                             'transitions': {}}}


class TestValidateLoginEmail:

    @fixture
    def request_(self, request_):
        request_.validated['email'] = 'user@example.org'
        return request_

    def call_fut(self, context, request_):
        from adhocracy_core.rest.views import validate_login_email
        return validate_login_email(context, request_)

    def test_valid(self, request_, context, mock_user_locator):
        user = testing.DummyResource()
        mock_user_locator.get_user_by_email.return_value = user
        self.call_fut(context, request_)
        assert request_.validated['user'] == user

    def test_valid_email_with_capital_letters(self, request_, context, mock_user_locator):
        request_.validated['email'] = 'usER@example.org'
        user = testing.DummyResource()
        mock_user_locator.get_user_by_email.return_value = user
        self.call_fut(context, request_)
        mock_user_locator.get_user_by_email.assert_called_with('user@example.org')
        assert request_.validated['user'] == user

    def test_invalid(self, request_, context, mock_user_locator):
        mock_user_locator.get_user_by_email.return_value = None
        self.call_fut(context, request_)
        assert 'user' not in request_.validated
        assert 'User doesn\'t exist' in request_.errors[0].description


class TestValidateLoginNameUnitTest:

    @fixture
    def request_(self, request_):
        request_.validated['name'] = 'user'
        return request_

    def call_fut(self, context, request_):
        from adhocracy_core.rest.views import validate_login_name
        return validate_login_name(context, request_)

    def test_invalid(self, request_, context, mock_user_locator):
        mock_user_locator.get_user_by_login.return_value = None
        self.call_fut(context, request_)
        assert 'User doesn\'t exist' in request_.errors[0].description

    def test_valid(self, request_, context, mock_user_locator):
        user = testing.DummyResource()
        mock_user_locator.get_user_by_login.return_value = user
        self.call_fut(context, request_)
        assert request_.validated['user'] == user


class TestValidateLoginPasswordUnitTest:

    @fixture
    def request_(self, request_):
        from adhocracy_core.sheets.principal import IPasswordAuthentication
        user = testing.DummyResource(__provides__=IPasswordAuthentication)
        request_.validated['user'] = user
        request_.validated['password'] = 'lalala'
        return request_

    def call_fut(self, context, request_):
        from adhocracy_core.rest.views import validate_login_password
        return validate_login_password(context, request_)

    def test_valid(self, request_, context, mock_password_sheet):
        sheet = mock_password_sheet
        sheet.check_plaintext_password.return_value = True
        self.call_fut(context, request_)
        assert request_.errors == []

    def test_invalid(self, request_, context, mock_password_sheet):
        sheet = mock_password_sheet
        sheet.check_plaintext_password.return_value = False
        self.call_fut(context, request_)
        assert 'password is wrong' in request_.errors[0].description

    def test_invalid_with_ValueError(self, request_, context, mock_password_sheet):
        sheet = mock_password_sheet
        sheet.check_plaintext_password.side_effect = ValueError
        self.call_fut(context, request_)
        assert 'password is wrong' in request_.errors[0].description

    def test_user_is_None(self, request_, context):
        request_.validated['user'] = None
        self.call_fut(context, request_)
        assert request_.errors == []


class TestValidateAccountActiveUnitTest:

    def call_fut(self, context, request):
        from adhocracy_core.rest.views import validate_account_active
        return validate_account_active(context, request)

    def test_valid(self, request_, context):
        user = testing.DummyResource(active=True)
        request_.validated['user'] = user
        self.call_fut(context, request_)
        assert not request_.errors

    def test_invalid(self, request_, context):
        user = testing.DummyResource(active=False)
        request_.validated['user'] = user
        self.call_fut(context, request_)
        assert 'not yet activated' in request_.errors[0].description

    def test_no_error_added_after_other_errors(self, request_, context):
        user = testing.DummyResource(active=False)
        request_.validated['user'] = user
        request_.errors.append(('blah', 'blah', 'blah'))
        assert len(request_.errors) == 1
        self.call_fut(context, request_)
        assert len(request_.errors) == 1


class TestLoginUserName:

    @fixture
    def request(self, request_):
        request_.validated['user'] = testing.DummyResource()
        request_.validated['password'] = 'lalala'
        return request_

    def make_one(self, request, context):
        from adhocracy_core.rest.views import LoginUsernameView
        return LoginUsernameView(request, context)

    def test_post_without_token_authentication_policy(self, request, context):
        inst = self.make_one(context, request)
        with pytest.raises(KeyError):
            inst.post()

    def test_post_with_token_authentication_policy(self, request, context, mock_authpolicy):
        mock_authpolicy.remember.return_value = {'X-User-Path': '/user',
                                                 'X-User-Token': 'token'}
        inst = self.make_one(context, request)
        assert inst.post() == {'status': 'success',
                               'user_path': '/user',
                               'user_token': 'token'}

    def test_options(self, request, context):
        inst = self.make_one(context, request)
        assert inst.options() == {}


class TestLoginEmailView:

    @fixture
    def request(self, request_):
        request_.validated['user'] = testing.DummyResource()
        return request_

    def make_one(self, context, request):
        from adhocracy_core.rest.views import LoginEmailView
        return LoginEmailView(context, request)

    def test_post_without_token_authentication_policy(self, request, context):
        inst = self.make_one(context, request)
        with pytest.raises(KeyError):
            inst.post()

    def test_post_with_token_authentication_policy(self, request, context, mock_authpolicy):
        mock_authpolicy.remember.return_value = {'X-User-Path': '/user',
                                                 'X-User-Token': 'token'}
        inst = self.make_one(context, request)
        assert inst.post() == {'status': 'success',
                               'user_path': '/user',
                               'user_token': 'token'}

    def test_options(self, request, context):
        inst = self.make_one(context, request)
        assert inst.options() == {}



class TestValidateActivationPathUnitTest:

    @fixture
    def _request(self, request_, registry):
        request_.registry = registry
        request_.validated['path'] = '/foo'
        return request_

    @fixture
    def user(self):
        user = testing.DummyResource()
        user.activate = Mock()
        return user

    def call_fut(self, context, _request):
        from adhocracy_core.rest.views import validate_activation_path
        return validate_activation_path(context, _request)

    def test_valid(self, _request, user, context,
                   mock_user_locator):
        from datetime import datetime
        from datetime import timezone
        mock_user_locator.get_user_by_activation_path.return_value = user
        user.creation_date = datetime.now(timezone.utc)
        self.call_fut(context, _request)
        assert _request.validated['user'] == user
        assert user.activate.called

    def test_not_found(self, _request, context, mock_user_locator):
        mock_user_locator.get_user_by_activation_path.return_value = None
        self.call_fut(context, _request)
        assert 'Unknown or expired activation path' == _request.errors[0].description

    def test_found_but_expired(self, _request, user, context,
                               mock_user_locator):
        from datetime import datetime
        from datetime import timezone
        mock_user_locator.get_user_by_activation_path.return_value = user
        user.creation_date = datetime(year=2010, month=1, day=1, tzinfo=timezone.utc)
        self.call_fut(context, _request)
        self.call_fut(context, _request)
        assert 'Unknown or expired activation path' == _request.errors[0].description


class TestActivateAccountView:

    @fixture
    def request(self, request_):
        request_.validated['user'] = testing.DummyResource()
        return request_

    def make_one(self, context, request):
        from adhocracy_core.rest.views import ActivateAccountView
        return ActivateAccountView(context, request)

    def test_post(self, request, context, mock_authpolicy):
        mock_authpolicy.remember.return_value = {'X-User-Path': '/user',
                                                 'X-User-Token': 'token'}
        inst = self.make_one(context, request)
        assert inst.post() == {'status': 'success',
                               'user_path': '/user',
                               'user_token': 'token'}

    def test_options(self, request, context):
        inst = self.make_one(context, request)
        assert inst.options() == {}


class TestReportAbuseView:

    @fixture
    def request(self, request_):
        from adhocracy_core.messaging import Messenger
        request_.registry.messenger = Mock(spec=Messenger)
        request_.validated['url'] = 'http://localhost/blablah'
        request_.validated['remark'] = 'Too much blah!'
        return request_

    def make_one(self, context, request):
        from adhocracy_core.rest.views import ReportAbuseView
        return ReportAbuseView(context, request)

    def test_post(self, request, context):
        inst = self.make_one(context, request)
        assert inst.post() == ''
        assert request.registry.messenger.send_abuse_complaint.called

    def test_options(self, request, context):
        inst = self.make_one(context, request)
        assert inst.options() == {}


class TestMessageUserView:

    @fixture
    def request(self, request_):
        from adhocracy_core.messaging import Messenger
        request_.registry.messenger = Mock(spec=Messenger)
        request_.validated['recipient'] = testing.DummyResource()
        request_.validated['title'] = 'Important Adhocracy notice'
        request_.validated['text'] = 'Surprisingly enough, all is well.'
        return request_

    def make_one(self, context, request):
        from adhocracy_core.rest.views import MessageUserView
        return MessageUserView(context, request)

    def test_post(self, request, context):
        inst = self.make_one(context, request)
        assert inst.post() == ''
        assert request.registry.messenger.send_message_to_user.called

    def test_options_with_permission(self, request, context):
        inst = self.make_one(context, request)
        result = inst.options()
        assert 'POST' in result
        assert result['POST']['request_body'] == {'recipient': None,
                                                  'text': '',
                                                  'title': ''}
        assert result['POST']['response_body'] == ''

    def test_options_without_permission(self, request, context):
        from pyramid.request import Request
        request.has_permission = Mock(spec=Request.has_permission,
                                      return_value=False)
        inst = self.make_one(context, request)
        assert inst.options() == {}


class TestAssetsServiceRESTView:

    def make_one(self, context, request):
        from adhocracy_core.rest.views import AssetsServiceRESTView
        return AssetsServiceRESTView(context, request)

    def test_create(self, context, request_):
        from .views import SimpleRESTView
        from .schemas import POSTAssetRequestSchema
        inst = self.make_one(context, request_)
        assert issubclass(inst.__class__, SimpleRESTView)
        assert inst.validation_POST == (POSTAssetRequestSchema, [])

    def test_post_valid(self, request_, context):
        request_.root = context
        context['child'] = testing.DummyResource(__provides__=IResourceX)
        request_.registry.content.create.return_value = context['child']
        request_.validated = {'content_type': IResourceX, 'data': {}}
        inst = self.make_one(context, request_)
        response = inst.post()
        wanted = {'path': request_.application_url + '/child/',
                  'content_type': IResourceX.__identifier__,
                  'updated_resources': {'changed_descendants': [],
                                        'created': [],
                                        'modified': [],
                                        'removed': []}}
        assert wanted == response


class TestAssetRESTView:

    def make_one(self, context, request):
        from adhocracy_core.rest.views import AssetRESTView
        return AssetRESTView(context, request)

    def test_create(self, context, request_):
        from .views import SimpleRESTView
        from .schemas import PUTAssetRequestSchema
        inst = self.make_one(context, request_)
        assert issubclass(inst.__class__, SimpleRESTView)
        assert inst.validation_PUT == (PUTAssetRequestSchema, [])

    def test_put_valid_no_sheets(self, request_, context):
        inst = self.make_one(context, request_)
        response = inst.put()

        wanted = {'path': request_.application_url + '/',
                  'content_type': IResource.__identifier__,
                  'updated_resources': {'changed_descendants': [],
                                        'created': [],
                                        'modified': [],
                                        'removed': []}}
        assert wanted == response


class TestAssetDownloadRESTView:

    def make_one(self, context, request_):
        from adhocracy_core.rest.views import AssetDownloadRESTView
        return AssetDownloadRESTView(context, request_)

    def test_get(self, request_, context):
        context.get_response = Mock()
        inst = self.make_one(context, request_)
        inst.ensure_caching_headers = Mock()
        inst.get()
        context.get_response.assert_called_with(request_.registry)
        assert inst.ensure_caching_headers.called

    def test_ensure_caching_headers(self, context, request_):
        inst = self.make_one(context, request_)
        request_.response = testing.DummyResource(cache_control='cache_control',
                                                  etag='etag',
                                                  last_modified='last_modified')
        response = testing.DummyResource()
        inst.ensure_caching_headers(response)
        assert response.last_modified == 'last_modified'
        assert response.etag == 'etag'
        assert response.cache_control == 'cache_control'


class TestCreatePasswordResetView:

    @fixture
    def resets(self, context, service):
        context['resets'] = service

    @fixture
    def request_(self, request_):
        request_.validated['user'] = testing.DummyResource()
        return request_

    @fixture
    def mock_remember(self, monkeypatch):
        from pyramid.security import remember
        from . import views
        mock_remember = Mock(spec=remember)
        monkeypatch.setattr(views, 'remember', mock_remember)
        return mock_remember

    def make_one(self, context, request):
        from adhocracy_core.rest.views import CreatePasswordResetView
        return CreatePasswordResetView(context, request)

    def test_create(self, context, request_):
        from .schemas import POSTCreatePasswordResetRequestSchema
        inst = self.make_one(context, request_)
        assert inst.validation_POST == (POSTCreatePasswordResetRequestSchema,
                                        [])

    def test_post(self, request_, context, registry, resets):
        from adhocracy_core.resources.principal import IPasswordReset
        inst = self.make_one(context, request_)
        reset = testing.DummyResource(__name__='reset')
        registry.content.create.return_value = reset
        result = inst.post()
        registry.content.create.assert_called_with(
            IPasswordReset.__identifier__,
            resets,
            creator=request_.validated['user'])
        assert result == {'status': 'success'}

    def test_options(self, request_, context):
        inst = self.make_one(context, request_)
        assert inst.options() == {'POST': {}}


class TestPasswordResetView:

    @fixture
    def mock_remember(self, monkeypatch):
        from pyramid.security import remember
        from . import views
        mock_remember = Mock(spec=remember)
        monkeypatch.setattr(views, 'remember', mock_remember)
        return mock_remember

    def make_one(self, context, request):
        from adhocracy_core.rest.views import PasswordResetView
        return PasswordResetView(context, request)

    def test_create(self, context, request_):
        from .schemas import POSTPasswordResetRequestSchema
        inst = self.make_one(context, request_)
        assert inst.validation_POST == (POSTPasswordResetRequestSchema,
                                        [])

    def test_post(self, request_, context, mock_remember):
        from adhocracy_core.resources.principal import PasswordReset
        mock_reset = Mock(spec=PasswordReset)
        request_.validated['user'] = testing.DummyResource()
        request_.validated['path'] = mock_reset
        request_.validated['password'] = 'password'
        mock_remember.return_value = {'X-User-Path': '/',
                                      'X-User-Token': 'token'}
        inst = self.make_one(context, request_)
        result = inst.post()
        mock_reset.reset_password.assert_called()
        mock_remember.assert_called_with(request_, '/')
        mock_reset.reset_password.assert_called_with('password')
        assert result == {'status': 'success',
                          'user_path': '/',
                          'user_token': 'token'}

    def test_options(self, request_, context):
        inst = self.make_one(context, request_)
        assert inst.options() == {'POST': {}}


@fixture()
def integration(config):
    config.include('adhocracy_core.rest.views')


@mark.usefixtures('integration')
class TestIntegrationIncludeme:

    def test_includeme(self):
        """Check that includeme runs without errors."""
        assert True


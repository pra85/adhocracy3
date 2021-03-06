"""Scripts to migrate legacy objects in existing databases."""
import logging  # pragma: no cover

from substanced.util import find_service

from adhocracy_core.evolution import log_migration
from adhocracy_core.evolution import migrate_new_sheet
from adhocracy_core.evolution import _search_for_interfaces
from adhocracy_core.utils import get_sheet
from adhocracy_meinberlin.resources.kiezkassen import IProposalVersion
import adhocracy_core.sheets
import adhocracy_meinberlin.sheets

logger = logging.getLogger(__name__)  # pragma: no cover


def use_adhocracy_core_title_sheet(root):  # pragma: no cover
    """Migrate kiezkassen proposal to adhocracy_core title sheet.

    Add title sheet.
    Remove title field from proposal sheet.
    """
    migrate_new_sheet(root, IProposalVersion,
                      adhocracy_core.sheets.title.ITitle,
                      adhocracy_meinberlin.sheets.kiezkassen.IProposal,
                      remove_isheet_old=False,
                      fields_mapping=[('title', 'title')])


def use_adhocracy_core_description_sheet(root):  # pragma: no cover
    """Migrate kiezkassen proposal to description sheet.

    Add description sheet.
    Remove detail field from proposal sheet.
    """
    migrate_new_sheet(root, IProposalVersion,
                      adhocracy_core.sheets.description.IDescription,
                      adhocracy_meinberlin.sheets.kiezkassen.IProposal,
                      remove_isheet_old=False,
                      fields_mapping=[('description', 'detail')])


@log_migration
def remove_meinberlin_workflow_assignment_sheets(root):  # pragma: no cover
    """Remove deprecated sheets.bplan/kiezkasse.IWorkflowAssignment."""
    from adhocracy_core.interfaces import IResource
    from adhocracy_core.sheets.workflow import IWorkflowAssignment
    from adhocracy_meinberlin import sheets
    migrate_new_sheet(root,
                      IResource,
                      IWorkflowAssignment,
                      sheets.bplan.IWorkflowAssignment,
                      remove_isheet_old=True,
                      )
    migrate_new_sheet(root,
                      IResource,
                      IWorkflowAssignment,
                      sheets.bplan.IPrivateWorkflowAssignment,
                      remove_isheet_old=True,
                      )
    migrate_new_sheet(root,
                      IResource,
                      IWorkflowAssignment,
                      sheets.kiezkassen.IWorkflowAssignment,
                      remove_isheet_old=True,
                      )


@log_migration
def change_bplan_officeworker_email_representation(root):  # pragma: no cover
    """Change bplan officeworker email representation."""
    from substanced.util import find_objectmap
    from adhocracy_core.utils import find_graph
    from adhocracy_meinberlin.resources.bplan import IProcess
    from adhocracy_meinberlin.sheets.bplan import IProcessSettings
    from adhocracy_meinberlin.sheets.bplan import IProcessPrivateSettings
    from adhocracy_meinberlin.sheets.bplan import OfficeWorkerUserReference
    migrate_new_sheet(root, IProcess, IProcessPrivateSettings)
    catalogs = find_service(root, 'catalogs')
    bplaene = _search_for_interfaces(catalogs, IProcess)
    objectmap = find_objectmap(root)
    graph = find_graph(root)
    for bplan in bplaene:
        office_worker = graph.get_references_for_isheet(
            bplan,
            IProcessSettings)['office_worker'][0]
        private_settings = get_sheet(bplan, IProcessPrivateSettings)
        private_settings.set({'office_worker_email': office_worker.email})
        objectmap.disconnect(bplan, office_worker, OfficeWorkerUserReference)


def includeme(config):  # pragma: no cover
    """Register evolution utilities and add evolution steps."""
    config.add_evolution_step(use_adhocracy_core_title_sheet)
    config.add_evolution_step(use_adhocracy_core_description_sheet)
    config.add_evolution_step(remove_meinberlin_workflow_assignment_sheets)
    config.add_evolution_step(change_bplan_officeworker_email_representation)

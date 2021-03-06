import * as AdhConfig from "../../Config/Config";

export var pkgLocation = "/Meinberlin/Phase";


export interface IPhase {
    name : string;
    title : string;
    shorttitle? : string;
    description : string;
    processType : string;
    votingAvailable : boolean;
    commentAvailable : boolean;
    startDate? : string;
    endDate? : string;
}

export interface IPhaseHeaderScope {
    currentPhase : string;
    phases : IPhase[];
}


export var phaseDirective = (adhConfig : AdhConfig.IService) => {
    return {
        restrict: "E",
        templateUrl: adhConfig.pkg_path + pkgLocation + "/Phase.html",
        scope: {
            phase: "="
        }
    };
};

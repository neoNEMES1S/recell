function mdl = build_battery_model(caseDirectory, outputDirectory)
% Source handoff: requires MATLAB/Simulink/Simscape R2025a or later.
% Not executed or product-validated in the current Python-only environment.
arguments
    caseDirectory (1,1) string
    outputDirectory (1,1) string
end
assert(~verLessThan('matlab','25.1'), 'R2025a or later is required');
assert(license('test','Simulink') && license('test','Simscape'), ...
    'Licensed Simulink and Simscape are required');
assert(~isfolder(outputDirectory), 'Choose a fresh output directory');
mkdir(outputDirectory);
sourceDirectory = fileparts(mfilename('fullpath'));
addpath(sourceDirectory);
old = pwd; cleanup = onCleanup(@() cd(old));
cd(outputDirectory);
copyfile(fullfile(sourceDirectory,'+recell'), '+recell');
ssc_build('recell');
caseData = load(fullfile(caseDirectory,'case.mat'));
mdl = "recell_pulse_validation";
assert(~bdIsLoaded(mdl), 'Close the existing validation model first');
new_system(mdl);
load_system('recell_lib'); load_system('fl_lib'); load_system('nesl_utility');
add_block('recell_lib/Cell1RC', mdl+'/Cell');
for name = ["r0","r1","tau","ocv","v_initial"]
    set_param(mdl+'/Cell',name,num2str(caseData.(name),17));
end
add_block('simulink/Sources/From Workspace',mdl+'/Current', ...
    'VariableName','recell_current','Interpolate','off');
add_block('nesl_utility/Simulink-PS Converter',mdl+'/ToPhysical','Unit','A');
add_block('fl_lib/Electrical/Electrical Sources/Controlled Current Source',mdl+'/Load');
add_block('fl_lib/Electrical/Electrical Sensors/Voltage Sensor',mdl+'/Voltage');
add_block('fl_lib/Electrical/Electrical Elements/Electrical Reference',mdl+'/Ground');
add_block('nesl_utility/Solver Configuration',mdl+'/Solver');
add_block('nesl_utility/PS-Simulink Converter',mdl+'/ToSimulink','Unit','V');
add_block('simulink/Sinks/To Workspace',mdl+'/RecordedVoltage', ...
    'VariableName','recell_voltage','SaveFormat','Timeseries');
add_line(mdl,'Current/1','ToPhysical/1');
add_line(mdl,'ToSimulink/1','RecordedVoltage/1');
simscape.addConnection(mdl+'/ToPhysical','output',mdl+'/Load','iT');
simscape.addConnection(mdl+'/Load','head',mdl+'/Cell','p');
simscape.addConnection(mdl+'/Load','tail',mdl+'/Cell','n');
simscape.addConnection(mdl+'/Cell','p',mdl+'/Voltage','p');
simscape.addConnection(mdl+'/Cell','n',mdl+'/Voltage','n');
simscape.addConnection(mdl+'/Cell','n',mdl+'/Ground','V');
simscape.addConnection(mdl+'/Cell','n',mdl+'/Solver','port');
simscape.addConnection(mdl+'/Voltage','V',mdl+'/ToSimulink','input');
assignin('base','recell_current',[caseData.time_s,caseData.current_a]);
assignin('base','recell_times',caseData.time_s);
set_param(mdl,'Solver','ode23t','StopTime',num2str(caseData.time_s(end),17), ...
    'RelTol','1e-8','AbsTol','1e-10','OutputOption','SpecifiedOutputTimes', ...
    'OutputTimes','recell_times','ReturnWorkspaceOutputs','on');
save_system(mdl,fullfile(outputDirectory,mdl+'.slx'));
end

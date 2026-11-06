function result = run_validation(caseDirectory, outputDirectory)
% This function can only produce an execution result on a licensed MATLAB host.
arguments
    caseDirectory (1,1) string
    outputDirectory (1,1) string
end
caseDirectory = string(java.io.File(caseDirectory).getCanonicalPath());
outputDirectory = string(java.io.File(outputDirectory).getCanonicalPath());
mdl = build_battery_model(caseDirectory,outputDirectory);
cleanup = onCleanup(@() close_system(mdl,0));
c = load(fullfile(caseDirectory,'case.mat'));
values = zeros(numel(c.time_s),2);
steps = [.02,.01];
for k = 1:2
    simulation = sim(mdl,'MaxStep',num2str(steps(k),17));
    logged = simulation.get('recell_voltage');
    [found,index] = ismembertol(c.time_s,logged.Time,1e-10,'DataScale',1);
    assert(all(found),'Requested sample clock missing; do not interpolate across pulses');
    values(:,k) = logged.Data(index);
end
error = max(abs(values(:,2)-c.python_v));
convergence = max(abs(values(:,1)-values(:,2)));
assert(error < 1e-4 && convergence < 1e-4, ...
    'Numerical verification failed: check load orientation, hold convention and solver');
writetable(table(c.time_s,c.measured_v,c.python_v,values(:,2), ...
    'VariableNames',{'time_s','measured_v','python_v','simscape_v'}), ...
    fullfile(outputDirectory,'trajectories.csv'));
result = struct('status','completed','matlab_executed',true, ...
    'release',version('-release'),'products',{ver}, ...
    'max_python_difference_v',error,'max_solver_difference_v',convergence, ...
    'scope','local pulse numerical verification; not independent physical validation');
fid = fopen(fullfile(outputDirectory,'execution.json'),'w');
assert(fid >= 0,'Unable to create execution record');
closer = onCleanup(@() fclose(fid)); fprintf(fid,'%s',jsonencode(result));
end

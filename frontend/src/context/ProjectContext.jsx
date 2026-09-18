import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { getUserProjectConfig } from "../api";

const ProjectContext = React.createContext();

const ProjectProvider = ({ children }) => {
    const [projectName, setProjectName] = useState(() => {
        const savedProjectName = localStorage.getItem("project-name");
        return savedProjectName || "";
    });
    const [projectConfigured, setProjectConfigured] = useState(false);
    const [checkingConfig, setCheckingConfig] = useState(false);
 

    // Sync to localStorage whenever projectName changes
    useEffect(() => {
        if (projectName) {
            localStorage.setItem("project-name", projectName);
        }
    }, [projectName]);

    // Check whether this project has a saved config whenever the name changes
    useEffect(() => {
        if (!projectName) {
            setProjectConfigured(false);
            return;
        }
        let cancelled = false;
        setCheckingConfig(true);
        getUserProjectConfig(projectName)
            .then((cfg) => {
                if (!cancelled) {
                    const hasConfig = !!(cfg && ((cfg.cell_iids && cfg.cell_iids.length > 0) || (cfg.cords && cfg.cords.length > 0)) && cfg.cords && cfg.cords.length >= 3);
                    setProjectConfigured(hasConfig);
                }
            })
            .catch(() => {
                if (!cancelled) setProjectConfigured(false);
            })
            .finally(() => {
                if (!cancelled) setCheckingConfig(false);
            });
        return () => { cancelled = true; };
    }, [projectName]);

    const refreshProjectConfigured = useCallback(() => {
        if (!projectName) return;
        getUserProjectConfig(projectName)
            .then((cfg) => {
                const hasConfig = !!(cfg && ((cfg.cell_iids && cfg.cell_iids.length > 0) || (cfg.cords && cfg.cords.length > 0)) && cfg.cords && cfg.cords.length >= 3);
                setProjectConfigured(hasConfig);
            })
            .catch(() => setProjectConfigured(false));
    }, [projectName]);

    return (
        <ProjectContext.Provider value={{ projectName, setProjectName, projectConfigured, checkingConfig, refreshProjectConfigured }}>
            {children}
        </ProjectContext.Provider>
    );
};

const useProjectContext = () => {
    return useContext(ProjectContext);
};

export { ProjectProvider, useProjectContext };
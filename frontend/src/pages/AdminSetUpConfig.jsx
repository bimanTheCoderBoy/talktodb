import React from 'react';
import ProjectConfigModal from '@/components/project_config/ProjectConfigModal';

function AdminSetUpConfig() {
  return (
    <ProjectConfigModal
      isOpen={true}
      onClose={() => window.history.back()}
      projectName=""
    />
  );
}

export default AdminSetUpConfig;

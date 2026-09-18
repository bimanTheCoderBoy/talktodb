import { useACSSContext } from '@/acss_module/context/ACSSContext';
import { Setup } from '@/acss_module/components/setup';
import { useState } from 'react';
import { X } from 'lucide-react';
const AcssSetupModal = ({isOpen, onClose }) => {
    const { setupState } = useACSSContext();
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(false);
    const [message, setMessage] = useState('');
    const [showMessage, setShowMessage] = useState(false);
    const [showSuccess, setShowSuccess] = useState(false);
    const [showError, setShowError] = useState(false);
  return (
    <div className='fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50 backdrop-blur-[2px]'>
      <div className='w-full max-w-md bg-card border border-border rounded-xl shadow-2xl shadow-black/50 flex flex-col overflow-hidden'>
        <div className='flex items-center justify-between p-3 border-b border-border bg-secondary/50'>
          <h1 className='text-2xl font-bold'>AspSetupModal</h1>
          <button onClick={onClose} className='p-1.5 hover:bg-accent rounded-lg transition-colors'>
            <X className='w-4 h-4 text-muted-foreground hover:text-foreground' />
          </button>
        </div>
        <h1 className='text-2xl font-bold'>AspSetupModal</h1>
      </div>
    </div>
  );
};

export default AcssSetupModal;
import { Handle, Position } from 'reactflow';
import { Router, Network, Server, HardDrive, Monitor, Radio, Wifi } from 'lucide-react';

export default function DeviceNode({ data }: any) {
  const isCritical = data.status === 'down';

  const getIcon = (category: string) => {
    switch (category.toLowerCase()) {
      case 'router': return <Router size={18} />;
      case 'switch': return <Network size={18} />;
      case 'counter': return <Monitor size={18} />;
      case 'ts': return <HardDrive size={18} />;
      case 'bts': return <Radio size={18} />;
      case 'modem': return <Wifi size={18} />;
      default: return <Server size={18} />;
    }
  };

  return (
    <div style={{
      background: isCritical ? 'rgba(239, 68, 68, 0.1)' : 'rgba(21, 30, 50, 0.95)',
      border: `2px solid ${isCritical ? 'var(--accent-red)' : 'var(--accent-blue)'}`,
      borderRadius: '10px', padding: '10px 14px', minWidth: '180px',
      boxShadow: isCritical ? '0 0 15px rgba(239, 68, 68, 0.4)' : '0 4px 6px -1px rgba(0,0,0,0.5)',
      backdropFilter: 'blur(8px)', color: 'white', position: 'relative'
    }}>
      <Handle type="target" position={Position.Top} style={{ background: '#64748b', width: '8px', height: '8px' }} />
      
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
        <span style={{ color: isCritical ? 'var(--accent-red)' : 'var(--accent-blue)' }}>{getIcon(data.category)}</span>
        <span style={{ fontWeight: 700, fontSize: '0.95rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '130px' }}>
          {data.label}
        </span>
      </div>
      
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'monospace', background: 'rgba(0,0,0,0.3)', padding: '2px 6px', borderRadius: '4px', display: 'inline-block' }}>
        {data.ip || 'No IP'}
      </div>

      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '4px', textTransform: 'uppercase', textAlign: 'right' }}>
        {data.category}
      </div>

      <Handle type="source" position={Position.Bottom} style={{ background: '#64748b', width: '8px', height: '8px' }} />
    </div>
  );
}
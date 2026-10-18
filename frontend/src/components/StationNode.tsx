import { Handle, Position } from 'reactflow';
import { AlertTriangle, CheckCircle, Wifi } from 'lucide-react';

export default function StationNode({ data }: any) {
  // डमी स्टेटस: अगर स्टेशन का कोड BSB या MB है, तो उसे 'Critical' दिखाएँ
  const isCritical = data.code === 'BSB' || data.code === 'MB'; 

  return (
    <div style={{
      background: isCritical ? 'rgba(239, 68, 68, 0.1)' : 'rgba(21, 30, 50, 0.95)',
      border: `2px solid ${isCritical ? 'var(--accent-red)' : 'var(--accent-blue)'}`,
      borderRadius: '10px',
      padding: '10px 14px',
      minWidth: '160px',
      boxShadow: isCritical ? '0 0 15px rgba(239, 68, 68, 0.4)' : '0 4px 6px -1px rgba(0,0,0,0.5)',
      backdropFilter: 'blur(8px)',
      color: 'white',
      position: 'relative'
    }}>
      {/* टॉप कनेक्शन पॉइंट */}
      <Handle type="target" position={Position.Top} style={{ background: '#64748b', width: '8px', height: '8px' }} />
      
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {isCritical ? (
          <AlertTriangle size={18} color="var(--accent-red)" />
        ) : (
          <CheckCircle size={18} color="var(--accent-green)" />
        )}
        <span style={{ fontWeight: 700, fontSize: '1rem', letterSpacing: '0.5px' }}>
          {data.code}
        </span>
      </div>
      
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {data.label}
      </div>
      
      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>{data.division}</span>
        <span style={{ background: 'rgba(59, 130, 246, 0.2)', padding: '2px 6px', borderRadius: '4px' }}>{data.tier}</span>
      </div>

      {/* बॉटम कनेक्शन पॉइंट */}
      <Handle type="source" position={Position.Bottom} style={{ background: '#64748b', width: '8px', height: '8px' }} />
    </div>
  );
}
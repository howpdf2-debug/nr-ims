import ReactFlow, { Background, Controls, MarkerType } from 'reactflow';
import type { Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';

const initialNodes: Node[] = [
  { id: 'BSB', data: { label: 'BSB' }, position: { x: 400, y: 300 }, style: { background: '#1e293b', color: '#fff', border: '2px solid #3b82f6' } },
  { id: 'LKO', data: { label: 'LKO' }, position: { x: 150, y: 150 }, style: { background: '#1e293b', color: '#fff' } },
  { id: 'PRG', data: { label: 'PRG' }, position: { x: 650, y: 150 }, style: { background: '#1e293b', color: '#fff' } },
];

const initialEdges: Edge[] = [
  { id: 'e1', source: 'BSB', target: 'LKO', label: 'OFC (1G)', animated: true, style: { stroke: '#10b981', strokeWidth: 8 } },
  { id: 'e2', source: 'BSB', target: 'PRG', label: 'BSNL (10M)', style: { stroke: '#ef4444', strokeWidth: 2 } },
];

export default function Topology() {
  return (
    <div style={{ height: '80vh', background: '#0b1121', borderRadius: '12px' }}>
      <ReactFlow nodes={initialNodes} edges={initialEdges} fitView>
        <Background color="#334155" gap={16} />
        <Controls />
      </ReactFlow>
    </div>
  );
}

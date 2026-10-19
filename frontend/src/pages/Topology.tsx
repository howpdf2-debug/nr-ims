import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import ReactFlow, { Background, Controls, MarkerType, useNodesState, useEdgesState } from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import { api } from "../lib/api";
import StationNode from "../components/StationNode";
import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Search, ShieldAlert, User, X, Power, RotateCcw, AlertTriangle } from "lucide-react";

const nodeTypes = { customNode: StationNode };
const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));
const nodeWidth = 172; const nodeHeight = 80;

const getLayoutedElements = (nodes: any[], edges: any[], direction = 'TB') => {
  dagreGraph.setGraph({ rankdir: direction, ranksep: 100, nodesep: 50 });
  nodes.forEach((node) => { dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight }); });
  edges.forEach((edge) => { dagreGraph.setEdge(edge.source, edge.target); });
  dagre.layout(dagreGraph);
  return nodes.map((node) => {
    const pos = dagreGraph.node(node.id);
    if (node.position.x !== 0 && node.position.y !== 0) return node;
    return { ...node, position: { x: pos.x - nodeWidth / 2, y: pos.y - nodeHeight / 2 } };
  });
};

export default function Topology() {
  const queryClient = useQueryClient();
  const navigate = useNavigate(); // <-- Drill-down के लिए
  const [isAdminMode, setIsAdminMode] = useState(false);
  const [selectedEdge, setSelectedEdge] = useState<any>(null);
  const [searchTerm, setSearchTerm] = useState("");

  const token = localStorage.getItem("token");
  let userRole = "operator";
  if (token) { try { userRole = JSON.parse(atob(token.split('.')[1])).role || "operator"; } catch (e) {} }
  const canBeAdmin = userRole.includes("admin");

  const { data, isLoading, isError } = useQuery({ queryKey: ["topology"], queryFn: () => api.get("/topology/").then(res => res.data) });
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    if (data && data.nodes) {
      const styledEdges = (data.edges || []).map((edge: any) => {
        let color = '#10b981'; let isAnimated = true;
        if (edge.data.status === 'down') { color = '#ef4444'; isAnimated = false; } 
        else if (edge.data.status === 'degraded') { color = '#f59e0b'; isAnimated = false; }
        return { ...edge, animated: isAnimated, style: { stroke: color, strokeWidth: edge.data.provider === 'Railway' ? 4 : 2, strokeDasharray: edge.data.status === 'degraded' ? '5,5' : '0' }, markerEnd: { type: MarkerType.ArrowClosed, color } };
      });
      setNodes(getLayoutedElements(data.nodes, styledEdges));
      setEdges(styledEdges);
    }
  }, [data, setNodes, setEdges]);

  const toggleLinkMutation = useMutation({
    mutationFn: ({ id, status, is_admin }: { id: string, status: string, is_admin: boolean }) => api.put(`/topology/links/${id}/status`, { status, is_admin }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["topology"] }); setSelectedEdge(null); }
  });

  const onNodeClick = useCallback((event: any, node: any) => { navigate(`/station/${node.id}`); }, [navigate]);
  const onEdgeClick = useCallback((event: any, edge: any) => { setSelectedEdge(edge); }, []);

  const filteredNodes = searchTerm ? nodes.filter(n => n.data.code.toLowerCase().includes(searchTerm.toLowerCase())) : nodes;

  if (isLoading) return <p style={{ padding: '2rem' }}>Loading live topology...</p>;
  if (isError) return <p style={{ color: 'red', padding: '2rem' }}>Error loading topology.</p>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '80vh', position: 'relative' }}>
      <div style={{ padding: '1rem', background: 'var(--bg-surface)', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', width: '40%' }}>
          <Search size={20} color="var(--text-muted)" />
          <input type="text" placeholder="Search Station..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} style={{ background: 'transparent', border: 'none', color: 'white', outline: 'none', width: '100%' }} />
        </div>
        
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          {canBeAdmin ? (
            <div style={{ display: 'flex', background: 'var(--bg-base)', borderRadius: '8px', padding: '4px', border: '1px solid var(--border-color)' }}>
              <button onClick={() => setIsAdminMode(false)} style={{ padding: '0.4rem 1rem', borderRadius: '6px', border: 'none', cursor: 'pointer', background: !isAdminMode ? 'var(--accent-blue)' : 'transparent', color: 'white', fontWeight: 600 }}>Operator</button>
              <button onClick={() => setIsAdminMode(true)} style={{ padding: '0.4rem 1rem', borderRadius: '6px', border: 'none', cursor: 'pointer', background: isAdminMode ? 'var(--accent-red)' : 'transparent', color: 'white', fontWeight: 600 }}>Admin Mode</button>
            </div>
          ) : <span>Read-Only</span>}
        </div>
      </div>

      <div style={{ flex: 1, background: '#0b1121', display: 'flex' }}>
        <div style={{ flex: 1 }}>
          <ReactFlow nodes={filteredNodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onNodeClick={onNodeClick} onEdgeClick={onEdgeClick} nodeTypes={nodeTypes} fitView onlyRenderVisibleElements={true}>
            <Background color="#334155" gap={16} /><Controls />
          </ReactFlow>
        </div>

        {selectedEdge && (
          <div style={{ width: '350px', background: 'var(--bg-surface)', borderLeft: '1px solid var(--border-color)', padding: '1.5rem', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <h2 style={{ margin: 0, fontSize: '1.2rem' }}>Circuit Details</h2>
              <button onClick={() => setSelectedEdge(null)} style={{ background: 'transparent', border: 'none', color: 'white', cursor: 'pointer' }}><X size={20}/></button>
            </div>
            <h3 style={{ color: selectedEdge.data.status === 'degraded' ? 'var(--accent-amber)' : selectedEdge.data.status === 'down' ? 'var(--accent-red)' : 'var(--accent-green)' }}>{selectedEdge.data.provider} ({selectedEdge.data.bandwidth} Mbps)</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1rem' }}>{selectedEdge.source} ↔ {selectedEdge.target}</p>
            <div style={{ background: 'var(--bg-base)', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}><span>Status:</span> <strong>{selectedEdge.data.status.toUpperCase()}</strong></div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}><span>Latency:</span> <strong>{selectedEdge.data.latency} ms</strong></div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}><span>Packet Loss:</span> <strong>{selectedEdge.data.packet_loss}%</strong></div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>CRC Errors:</span> <strong>{selectedEdge.data.crc}</strong></div>
            </div>
            {isAdminMode && (
              selectedEdge.data.status === 'down' ? (
                <button onClick={() => toggleLinkMutation.mutate({ id: selectedEdge.id, status: 'up', is_admin: false })} className="btn" style={{ background: 'var(--accent-green)' }}><RotateCcw size={16}/> Restore Link</button>
              ) : (
                <button onClick={() => toggleLinkMutation.mutate({ id: selectedEdge.id, status: 'down', is_admin: true })} className="btn btn-danger"><Power size={16}/> Force Failover</button>
              )
            )}
            {selectedEdge.data.status === 'degraded' && (
              <div style={{ marginTop: '1rem', background: 'rgba(245, 158, 11, 0.1)', color: 'var(--accent-amber)', padding: '1rem', borderRadius: '8px', fontSize: '0.85rem', border: '1px solid var(--accent-amber)' }}>
                <AlertTriangle size={16} style={{ display: 'inline', marginRight: '6px' }} /> Warning: High error rate. Consider Failover.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
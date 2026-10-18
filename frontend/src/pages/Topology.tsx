import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import ReactFlow, { Background, Controls, MarkerType, useNodesState, useEdgesState } from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import { api } from "../lib/api";
import StationNode from "../components/StationNode";
import { useEffect, useState, useCallback } from "react";
import { Search, Plus, Trash2, ShieldAlert, User, X, Shield } from "lucide-react";

const nodeTypes = { customNode: StationNode };
const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));
const nodeWidth = 172;
const nodeHeight = 80;

const getLayoutedElements = (nodes: any[], edges: any[], direction = 'TB') => {
  dagreGraph.setGraph({ rankdir: direction });
  nodes.forEach((node) => { dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight }); });
  edges.forEach((edge) => { dagreGraph.setEdge(edge.source, edge.target); });
  dagre.layout(dagreGraph);
  return nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    if (node.position.x !== 0 && node.position.y !== 0) return node;
    return { ...node, position: { x: nodeWithPosition.x - nodeWidth / 2, y: nodeWithPosition.y - nodeHeight / 2 } };
  });
};

export default function Topology() {
  const queryClient = useQueryClient();
  const [isAdminMode, setIsAdminMode] = useState(false);
  const [selectedEdge, setSelectedEdge] = useState<any>(null);
  const [searchTerm, setSearchTerm] = useState("");
  
  const [isLinkModalOpen, setIsLinkModalOpen] = useState(false);
  const [linkData, setLinkData] = useState({ source_station: "", destination_station: "", provider: "Railway", bandwidth_mbps: 1000 });

  // JWT Token से Role निकालें
  const token = localStorage.getItem("token");
  let userRole = "operator";
  if (token) {
    try { userRole = JSON.parse(atob(token.split('.')[1])).role || "operator"; } catch (e) {}
  }
  const canBeAdmin = userRole.includes("admin");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["topology"],
    queryFn: () => api.get("/topology/").then(res => res.data),
  });

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    if (data && data.nodes) {
      const styledEdges = (data.edges || []).map((edge: any) => {
        const isDown = edge.data.status === 'down';
        const isOFC = edge.data.provider === 'Railway';
        return {
          ...edge,
          animated: !isDown && isOFC,
          style: { stroke: isDown ? 'var(--accent-red)' : (isOFC ? 'var(--accent-green)' : 'var(--accent-amber)'), strokeWidth: isOFC ? 4 : 2 },
          markerEnd: { type: MarkerType.ArrowClosed, color: isDown ? 'var(--accent-red)' : (isOFC ? 'var(--accent-green)' : 'var(--accent-amber)') }
        };
      });
      setNodes(getLayoutedElements(data.nodes, styledEdges));
      setEdges(styledEdges);
    }
  }, [data, setNodes, setEdges]);

  const onNodeDragStop = useCallback(async (event: any, node: any) => {
    if (!isAdminMode) return;
    await api.put(`/topology/station/${node.id}/position`, { x: node.position.x, y: node.position.y });
  }, [isAdminMode]);

  const onEdgeClick = useCallback((event: any, edge: any) => {
    setSelectedEdge(edge);
  }, []);

  const filteredNodes = searchTerm 
    ? nodes.filter(n => n.data.code.toLowerCase().includes(searchTerm.toLowerCase()))
    : nodes;

  if (isLoading) return <p style={{ padding: '2rem' }}>Loading...</p>;
  if (isError) return <p style={{ color: 'red', padding: '2rem' }}>Error loading topology.</p>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '80vh', position: 'relative' }}>
      
      {/* Top Toolbar */}
      <div style={{ padding: '1rem', background: 'var(--bg-surface)', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', width: '40%' }}>
          <Search size={20} color="var(--text-muted)" />
          <input type="text" placeholder="Search Station..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} style={{ background: 'transparent', border: 'none', color: 'white', outline: 'none', width: '100%' }} />
        </div>
        
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          {canBeAdmin ? (
            <div style={{ display: 'flex', background: 'var(--bg-base)', borderRadius: '8px', padding: '4px', border: '1px solid var(--border-color)' }}>
              <button onClick={() => setIsAdminMode(false)} style={{ padding: '0.4rem 1rem', borderRadius: '6px', border: 'none', cursor: 'pointer', background: !isAdminMode ? 'var(--accent-blue)' : 'transparent', color: 'white', display: 'flex', gap: '6px', alignItems: 'center', fontWeight: 600 }}>
                <User size={16} /> Operator Mode
              </button>
              <button onClick={() => setIsAdminMode(true)} style={{ padding: '0.4rem 1rem', borderRadius: '6px', border: 'none', cursor: 'pointer', background: isAdminMode ? 'var(--accent-red)' : 'transparent', color: 'white', display: 'flex', gap: '6px', alignItems: 'center', fontWeight: 600 }}>
                <ShieldAlert size={16} /> Admin Mode
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', fontSize: '0.9rem' }}><Shield size={16} /> Read-Only</div>
          )}

          {isAdminMode && (
            <button onClick={() => setIsLinkModalOpen(true)} className="btn" style={{ width: 'auto', background: 'var(--accent-red)' }}><Plus size={16} /> Add Link</button>
          )}
        </div>
      </div>

      {/* Map Area */}
      <div style={{ flex: 1, background: '#0b1121', display: 'flex' }}>
        <div style={{ flex: 1 }}>
          <ReactFlow nodes={filteredNodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onNodeDragStop={onNodeDragStop} onEdgeClick={onEdgeClick} nodeTypes={nodeTypes} fitView>
            <Background color="#334155" gap={16} /><Controls />
          </ReactFlow>
        </div>

        {/* Link Details Side Panel */}
        {selectedEdge && (
          <div style={{ width: '300px', background: 'var(--bg-surface)', borderLeft: '1px solid var(--border-color)', padding: '1.5rem', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <h2 style={{ margin: 0, fontSize: '1.2rem' }}>Link Details</h2>
              <button onClick={() => setSelectedEdge(null)} style={{ background: 'transparent', border: 'none', color: 'white', cursor: 'pointer' }}><X size={20}/></button>
            </div>
            <h3 style={{ color: 'var(--accent-amber)' }}>Link {selectedEdge.source} ↔ {selectedEdge.target}</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
              Provider: {selectedEdge.data.provider}<br/>
              Bandwidth: {selectedEdge.data.bandwidth} Mbps<br/>
              Status: <strong style={{ color: selectedEdge.data.status === 'up' ? 'var(--accent-green)' : 'var(--accent-red)' }}>{selectedEdge.data.status.toUpperCase()}</strong>
            </p>
            {isAdminMode && (
              <button onClick={async () => {
                if(window.confirm("Delete this link permanently?")) {
                  await api.delete(`/topology/links/${selectedEdge.id}`);
                  queryClient.invalidateQueries({ queryKey: ["topology"] });
                  setSelectedEdge(null);
                }
              }} className="btn btn-danger" style={{ display: 'flex', gap: '8px', marginTop: 'auto' }}>
                <Trash2 size={16}/> Delete Link
              </button>
            )}
          </div>
        )}
      </div>

      {/* Add Link Modal */}
      {isLinkModalOpen && (
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
          <div className="data-card" style={{ width: '400px' }}>
            <h2 style={{ marginBottom: '1.5rem' }}>Add New Link (Admin)</h2>
            <div className="input-group"><label>Source (e.g. LKO)</label><input value={linkData.source_station} onChange={e => setLinkData({...linkData, source_station: e.target.value.toUpperCase()})} /></div>
            <div className="input-group"><label>Destination (e.g. BSB)</label><input value={linkData.destination_station} onChange={e => setLinkData({...linkData, destination_station: e.target.value.toUpperCase()})} /></div>
            <div className="input-group">
              <label>Provider</label>
              {/* यहाँ Railway OFC की जगह Railway कर दिया गया है */}
              <select value={linkData.provider} onChange={e => setLinkData({...linkData, provider: e.target.value})} style={{ padding: '0.75rem', borderRadius: '4px', background: 'var(--bg-base)', color: 'white', border: '1px solid var(--border-color)' }}>
                <option value="Railway">Railway</option>
                <option value="BSNL">BSNL</option>
                <option value="RAILTEL">RAILTEL</option>
              </select>
            </div>
            <div className="input-group"><label>Bandwidth (Mbps)</label><input type="number" value={linkData.bandwidth_mbps} onChange={e => setLinkData({...linkData, bandwidth_mbps: parseInt(e.target.value)})} /></div>
            <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem' }}>
              <button className="btn" onClick={() => {
                api.post("/topology/links", linkData).then(() => {
                  setIsLinkModalOpen(false);
                  queryClient.invalidateQueries({ queryKey: ["topology"] });
                });
              }}>Save Link</button>
              <button className="btn btn-danger" onClick={() => setIsLinkModalOpen(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
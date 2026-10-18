import { useState, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router-dom";
import ReactFlow, { 
  Background, Controls, MarkerType, useNodesState, useEdgesState,
  ConnectionLineType 
} from 'reactflow';
import type { Connection } from 'reactflow'; // <-- यहाँ import type किया गया है
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import { api } from "../lib/api";
import StationNode from "../components/StationNode";
import DeviceNode from "../components/DeviceNode";
import { ArrowLeft, List, Network, X, Link as LinkIcon, Plus, Trash2, ShieldAlert, User, Server, Filter } from "lucide-react";

const nodeTypes = { customNode: StationNode, deviceNode: DeviceNode };
const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));
const nodeWidth = 180;
const nodeHeight = 90;

const getLayoutedElements = (nodes: any[], edges: any[], direction = 'TB') => {
  dagreGraph.setGraph({ rankdir: direction, ranksep: 80, nodesep: 40 }); 
  nodes.forEach((node) => { dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight }); });
  edges.forEach((edge) => { dagreGraph.setEdge(edge.source, edge.target); });
  dagre.layout(dagreGraph);
  return nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    if (node.position.x !== 0 && node.position.y !== 0) return node;
    return { ...node, position: { x: nodeWithPosition.x - nodeWidth / 2, y: nodeWithPosition.y - nodeHeight / 2 } };
  });
};

export default function StationDetail() {
  const { code } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  
  const [viewMode, setViewMode] = useState<"list" | "topology">("list");
  const [isAdminMode, setIsAdminMode] = useState(false);
  const [filterCategory, setFilterCategory] = useState("all");
  
  const [isDeviceModalOpen, setIsDeviceModalOpen] = useState(false);
  const [isVisualConnectModalOpen, setIsVisualConnectModalOpen] = useState(false);
  
  const [deviceData, setDeviceData] = useState({ hostname: "", ip_address: "", category: "switch", parent_device_id: "" });
  const [visualLinkData, setVisualLinkData] = useState({ source_device_id: "", destination_device_id: "", media_type: "copper", description: "" });
  
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [selectedEdge, setSelectedEdge] = useState<any>(null);

  const token = localStorage.getItem("token");
  let userRole = "operator";
  if (token) { try { userRole = JSON.parse(atob(token.split('.')[1])).role || "operator"; } catch (e) {} }
  const canBeAdmin = userRole.includes("admin");

  const { data: devices = [], isLoading: loadingDevices } = useQuery({ queryKey: ["stationDevices", code], queryFn: () => api.get(`/devices/?station_code=${code}`).then(res => res.data) });
  const { data: localTopo, isLoading: loadingTopo } = useQuery({ queryKey: ["localTopology", code], queryFn: () => api.get(`/topology/local/${code}`).then(res => res.data), enabled: viewMode === "topology" });

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    if (localTopo && localTopo.nodes) {
      const styledEdges = (localTopo.edges || []).map((e: any) => {
        const isOFC = e.data.media_type === 'ofc';
        return { 
          ...e, label: e.label, 
          labelStyle: { fill: isOFC ? '#10b981' : '#f59e0b', fontWeight: 700, fontSize: 12 }, 
          labelBgStyle: { fill: '#1e293b', fillOpacity: 0.9 }, 
          style: { stroke: isOFC ? '#10b981' : '#f59e0b', strokeWidth: 3 }, 
          markerEnd: { type: MarkerType.ArrowClosed, color: isOFC ? '#10b981' : '#f59e0b' } 
        };
      });
      setNodes(getLayoutedElements(localTopo.nodes, styledEdges));
      setEdges(styledEdges);
    }
  }, [localTopo, setNodes, setEdges]);

  // Visual Connect Handler
  const onConnect = useCallback((params: Connection) => {
    if (!isAdminMode) return;
    setVisualLinkData({
      source_device_id: params.source || "",
      destination_device_id: params.target || "",
      media_type: "copper",
      description: ""
    });
    setIsVisualConnectModalOpen(true);
  }, [isAdminMode]);

  const deviceMutation = useMutation({ mutationFn: (data: any) => api.post("/devices/", data), onSuccess: () => { setIsDeviceModalOpen(false); queryClient.invalidateQueries({ queryKey: ["localTopology", code] }); } });
  const linkMutation = useMutation({ mutationFn: (data: any) => api.post("/topology/local/links", data), onSuccess: () => { setIsVisualConnectModalOpen(false); queryClient.invalidateQueries({ queryKey: ["localTopology", code] }); } });

  const deleteDevice = async (id: string) => {
    if(window.confirm("Delete this device permanently? (All connected links will also be deleted)")) {
      await api.delete(`/devices/${id}`);
      queryClient.invalidateQueries({ queryKey: ["localTopology", code] });
      setSelectedNode(null);
    }
  };

  const deleteLink = async (id: string) => {
    if(window.confirm("Delete this link permanently?")) {
      await api.delete(`/topology/local/links/${id}`);
      queryClient.invalidateQueries({ queryKey: ["localTopology", code] });
      setSelectedEdge(null);
    }
  };

  const onNodeDragStop = useCallback(async (event: any, node: any) => {
    if(!isAdminMode) return;
    await api.put(`/topology/local/device/${node.id}/position`, { x: node.position.x, y: node.position.y });
  }, [isAdminMode]);

  const onNodeClick = useCallback((event: any, node: any) => { setSelectedNode(node); setSelectedEdge(null); }, []);
  const onEdgeClick = useCallback((event: any, edge: any) => { setSelectedEdge(edge); setSelectedNode(null); }, []);

  const displayNodes = filterCategory === "all" ? nodes : nodes.filter(n => n.data.category === filterCategory || n.data.category === 'router'); 
  const displayEdges = edges.filter(e => displayNodes.find(n => n.id === e.source) && displayNodes.find(n => n.id === e.target));

  const getDeviceName = (id: string) => devices.find((d: any) => d.id === id)?.hostname || "Unknown";

  return (
    <div style={{ display: 'flex', height: '80vh', gap: '1rem' }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <button onClick={() => navigate(-1)} className="nav-item" style={{ display: 'inline-flex', background: 'transparent', border: 'none', color: 'var(--accent-blue)', cursor: 'pointer' }}>
            <ArrowLeft size={20} /> Back
          </button>
          
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            {viewMode === "topology" && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'var(--bg-surface)', padding: '4px 12px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                <Filter size={16} color="var(--text-muted)" />
                <select value={filterCategory} onChange={e => setFilterCategory(e.target.value)} style={{ background: 'transparent', border: 'none', color: 'white', outline: 'none', fontSize: '0.9rem' }}>
                  <option value="all" style={{ background: '#1e293b' }}>Show All</option>
                  <option value="switch" style={{ background: '#1e293b' }}>Only Switches</option>
                  <option value="counter" style={{ background: '#1e293b' }}>Only Counters</option>
                  <option value="bts" style={{ background: '#1e293b' }}>Only BTS</option>
                </select>
              </div>
            )}

            {canBeAdmin && (
              <div style={{ display: 'flex', background: 'var(--bg-surface)', borderRadius: '8px', padding: '4px', border: '1px solid var(--border-color)' }}>
                <button onClick={() => setIsAdminMode(false)} style={{ padding: '0.4rem 1rem', borderRadius: '6px', border: 'none', cursor: 'pointer', background: !isAdminMode ? 'var(--accent-blue)' : 'transparent', color: 'white', display: 'flex', gap: '6px', alignItems: 'center', fontWeight: 600 }}>
                  <User size={16} /> Operator
                </button>
                <button onClick={() => setIsAdminMode(true)} style={{ padding: '0.4rem 1rem', borderRadius: '6px', border: 'none', cursor: 'pointer', background: isAdminMode ? 'var(--accent-red)' : 'transparent', color: 'white', display: 'flex', gap: '6px', alignItems: 'center', fontWeight: 600 }}>
                  <ShieldAlert size={16} /> Admin Mode
                </button>
              </div>
            )}

            {isAdminMode && viewMode === "topology" && (
              <button onClick={() => setIsDeviceModalOpen(true)} className="btn" style={{ width: 'auto', background: 'var(--accent-blue)' }}><Plus size={16} /> Add Device</button>
            )}

            <div style={{ display: 'flex', background: 'var(--bg-surface)', borderRadius: '8px', padding: '4px', border: '1px solid var(--border-color)' }}>
              <button onClick={() => setViewMode("list")} style={{ padding: '0.5rem 1rem', borderRadius: '6px', border: 'none', cursor: 'pointer', background: viewMode === 'list' ? 'var(--accent-blue)' : 'transparent', color: 'white' }}><List size={16} /></button>
              <button onClick={() => setViewMode("topology")} style={{ padding: '0.5rem 1rem', borderRadius: '6px', border: 'none', cursor: 'pointer', background: viewMode === 'topology' ? 'var(--accent-blue)' : 'transparent', color: 'white' }}><Network size={16} /></button>
            </div>
          </div>
        </div>

        <h1 style={{ marginBottom: '1rem' }}>Station {code}</h1>
        {isAdminMode && viewMode === "topology" && (
          <p style={{ color: 'var(--accent-blue)', marginBottom: '1rem', fontSize: '0.9rem' }}>
            💡 <strong>Tip:</strong> Drag from the bottom dot of one device to the top dot of another device to create a link instantly!
          </p>
        )}

        {viewMode === "list" ? (
          <div className="data-card" style={{ padding: 0, overflow: 'hidden' }}>
            {loadingDevices ? <p style={{ padding: '1rem' }}>Loading...</p> : (
              <table className="data-table">
                <thead><tr><th>Hostname</th><th>IP</th><th>Category</th><th>Status</th><th>Action</th></tr></thead>
                <tbody>
                  {devices.map((d: any) => (
                    <tr key={d.id}>
                      <td style={{ fontWeight: 600 }}>{d.hostname}</td>
                      <td style={{ fontFamily: 'monospace' }}>{d.ip_address}</td>
                      <td style={{ textTransform: 'capitalize' }}>{d.category}</td>
                      <td><span className={`badge ${d.status === 'up' ? 'badge-up' : 'badge-down'}`}>{d.status}</span></td>
                      <td>{isAdminMode && <button onClick={() => deleteDevice(d.id)} className="btn btn-danger" style={{ padding: '4px 8px', width: 'auto' }}><Trash2 size={14}/></button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ) : (
          <div style={{ flex: 1, background: '#0b1121', borderRadius: '12px', border: '1px solid var(--border-color)', position: 'relative' }}>
            {loadingTopo ? <p style={{ padding: '2rem' }}>Loading Map...</p> : (
              <ReactFlow 
                nodes={displayNodes} edges={displayEdges} 
                onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} 
                onNodeDragStop={onNodeDragStop} 
                onNodeClick={onNodeClick} onEdgeClick={onEdgeClick} 
                onConnect={onConnect}
                connectionLineType={ConnectionLineType.SmoothStep}
                nodeTypes={nodeTypes} fitView
              >
                <Background color="#334155" gap={16} /><Controls />
              </ReactFlow>
            )}
          </div>
        )}
      </div>

      {(selectedNode || selectedEdge) && (
        <div style={{ width: '320px', background: 'var(--bg-surface)', borderLeft: '1px solid var(--border-color)', padding: '1.5rem', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
            <h2 style={{ margin: 0, fontSize: '1.2rem' }}>Details</h2>
            <button onClick={() => { setSelectedNode(null); setSelectedEdge(null); }} style={{ background: 'transparent', border: 'none', color: 'white', cursor: 'pointer' }}><X size={20} /></button>
          </div>

          {selectedNode && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', flex: 1 }}>
              <div style={{ background: 'var(--bg-base)', padding: '1rem', borderRadius: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1rem' }}>
                  <Server size={20} color="var(--accent-blue)" /><h3 style={{ margin: 0, color: 'var(--accent-blue)' }}>{selectedNode.data.label}</h3>
                </div>
                <p style={{ margin: '0 0 0.5rem', fontSize: '0.9rem' }}><strong>IP:</strong> {selectedNode.data.ip}</p>
                <p style={{ margin: '0 0 0.5rem', fontSize: '0.9rem' }}><strong>Type:</strong> {selectedNode.data.category.toUpperCase()}</p>
                <p style={{ margin: 0, fontSize: '0.9rem' }}><strong>Status:</strong> <span style={{ color: selectedNode.data.status === 'up' ? 'var(--accent-green)' : 'var(--accent-red)' }}>{selectedNode.data.status.toUpperCase()}</span></p>
              </div>
              {isAdminMode && <button onClick={() => deleteDevice(selectedNode.id)} className="btn btn-danger" style={{ display: 'flex', gap: '8px', marginTop: 'auto' }}><Trash2 size={16}/> Delete Device</button>}
            </div>
          )}

          {selectedEdge && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', flex: 1 }}>
              <div style={{ background: 'var(--bg-base)', padding: '1rem', borderRadius: '8px' }}>
                <h3 style={{ margin: '0 0 0.5rem 0', color: selectedEdge.data.media_type === 'ofc' ? '#10b981' : '#f59e0b' }}>{selectedEdge.data.media_type === 'ofc' ? 'Optical Fiber' : 'Copper Pair'}</h3>
                <p style={{ margin: 0, fontSize: '0.9rem' }}><strong>Src:</strong> {selectedEdge.data.source_host} ({selectedEdge.data.source_ip})</p>
                <p style={{ margin: 0, fontSize: '0.9rem' }}><strong>Dst:</strong> {selectedEdge.data.dest_host} ({selectedEdge.data.dest_ip})</p>
              </div>
              <p style={{ fontStyle: 'italic', fontSize: '0.9rem', color: 'var(--text-muted)' }}>"{selectedEdge.data.description || 'No description'}"</p>
              {isAdminMode && <button onClick={() => deleteLink(selectedEdge.id)} className="btn btn-danger" style={{ display: 'flex', gap: '8px', marginTop: 'auto' }}><Trash2 size={16}/> Delete Link</button>}
            </div>
          )}
        </div>
      )}

      {isVisualConnectModalOpen && (
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
          <div className="data-card" style={{ width: '400px' }}>
            <h2 style={{ marginBottom: '1rem' }}>Connect Devices</h2>
            <p style={{ marginBottom: '1.5rem', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
              Connecting <strong>{getDeviceName(visualLinkData.source_device_id)}</strong> to <strong>{getDeviceName(visualLinkData.destination_device_id)}</strong>
            </p>
            
            <div className="input-group">
              <label>Media Type</label>
              <select value={visualLinkData.media_type} onChange={e => setVisualLinkData({...visualLinkData, media_type: e.target.value})} style={{ padding: '0.75rem', borderRadius: '4px', background: 'var(--bg-base)', color: 'white', border: '1px solid var(--border-color)' }}>
                <option value="copper">Copper Pair (Cu)</option>
                <option value="ofc">Optical Fiber (OFC)</option>
              </select>
            </div>
            <div className="input-group"><label>Description</label><input value={visualLinkData.description} onChange={e => setVisualLinkData({...visualLinkData, description: e.target.value})} placeholder="e.g. Uplink" autoFocus /></div>
            
            <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem' }}>
              <button className="btn" onClick={() => linkMutation.mutate(visualLinkData)}>Connect</button>
              <button className="btn btn-danger" onClick={() => setIsVisualConnectModalOpen(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {isDeviceModalOpen && (
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
          <div className="data-card" style={{ width: '400px' }}>
            <h2 style={{ marginBottom: '1.5rem' }}>Add New Device</h2>
            <div className="input-group"><label>Hostname</label><input value={deviceData.hostname} onChange={e => setDeviceData({...deviceData, hostname: e.target.value})} placeholder="e.g. bsb-sw-3" /></div>
            <div className="input-group"><label>IP Address</label><input value={deviceData.ip_address} onChange={e => setDeviceData({...deviceData, ip_address: e.target.value})} placeholder="10.10.100.3" /></div>
            <div className="input-group"><label>Category</label><select value={deviceData.category} onChange={e => setDeviceData({...deviceData, category: e.target.value})} style={{ padding: '0.75rem', borderRadius: '4px', background: 'var(--bg-base)', color: 'white', border: '1px solid var(--border-color)' }}><option value="switch">Switch</option><option value="counter">Counter</option><option value="ts">Terminal Server (TS)</option><option value="bts">BTS</option><option value="modem">Modem</option><option value="router">Router</option></select></div>
            <div className="input-group"><label>Parent Device (Optional)</label><select value={deviceData.parent_device_id} onChange={e => setDeviceData({...deviceData, parent_device_id: e.target.value})} style={{ padding: '0.75rem', borderRadius: '4px', background: 'var(--bg-base)', color: 'white', border: '1px solid var(--border-color)' }}><option value="">None (Top Level)</option>{devices.map((opt: any) => <option key={opt.id} value={opt.id}>{opt.hostname}</option>)}</select></div>
            <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem' }}>
              <button className="btn" onClick={() => deviceMutation.mutate({ ...deviceData, station_code: code, parent_device_id: deviceData.parent_device_id || null })}>Save Device</button>
              <button className="btn btn-danger" onClick={() => setIsDeviceModalOpen(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
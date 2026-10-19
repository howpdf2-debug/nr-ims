import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { 
  Server, Activity, RotateCcw, Power, Terminal, 
  AlertTriangle, CheckCircle, ShieldAlert, X, Lock, Ban, Wrench
} from "lucide-react";

export default function ActionCenter() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  
  const [tab, setTab] = useState<"active" | "maintenance">("active");
  const [terminalOutput, setTerminalOutput] = useState<string | null>(null);
  
  const [isTelnetOpen, setIsTelnetOpen] = useState(false);
  const [telnetDevice, setTelnetDevice] = useState<any>(null);
  const [command, setCommand] = useState("");
  const [terminalHistory, setTerminalHistory] = useState<string[]>([]);
  const terminalEndRef = useRef<HTMLDivElement>(null);

  const [confirmStep, setConfirmStep] = useState(0);
  const [targetAction, setTargetAction] = useState<{ id: string, type: string, hostname: string } | null>(null);
  const [confirmText, setConfirmText] = useState("");

  const { data: downDevices = [], isLoading } = useQuery({
    queryKey: ["downDevices"],
    queryFn: () => api.get("/actions/down-devices").then(res => res.data),
    refetchInterval: 10000,
  });

  // टैब फ़िल्टर
  const filteredDevices = downDevices.filter((d: any) => 
    tab === "active" ? !d.is_maintenance : d.is_maintenance
  );

  const actionMutation = useMutation({
    mutationFn: (data: { device_id: string, action_type: string }) => api.post("/actions/execute", data),
    onSuccess: (res) => {
      setTerminalOutput(res.data.output);
      queryClient.invalidateQueries({ queryKey: ["downDevices"] });
      setTargetAction(null);
    },
    onError: () => alert("Action Failed!")
  });

  const maintenanceMutation = useMutation({
    mutationFn: ({ id, status }: { id: string, status: boolean }) => api.put(`/actions/${id}/maintenance`, { is_maintenance: status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["downDevices"] })
  });

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [terminalHistory]);

  const handleAction = (id: string, type: string, hostname: string) => {
    if (type === "PING") {
      setTerminalOutput(`Pinging ${hostname}...\nPlease wait...`);
      actionMutation.mutate({ device_id: id, action_type: type });
    } else {
      setTargetAction({ id, type, hostname });
      setConfirmStep(1);
    }
  };

  const nextConfirmStep = () => {
    if (confirmStep === 1) setConfirmStep(2);
    else if (confirmStep === 2) {
      if (confirmText.toUpperCase() === "CONFIRM") setConfirmStep(3);
      else alert("कृपया 'CONFIRM' शब्द सही से टाइप करें।");
    } else if (confirmStep === 3 && targetAction) {
      setTerminalOutput(`Executing ${targetAction.type} on ${targetAction.hostname}...\nPlease wait...`);
      actionMutation.mutate({ device_id: targetAction.id, action_type: targetAction.type });
      setConfirmStep(0);
      setTargetAction(null);
      setConfirmText("");
    }
  };

  const cancelConfirmation = () => {
    setConfirmStep(0);
    setTargetAction(null);
    setConfirmText("");
  };

  const handleTelnetOpen = (device: any) => {
    setTelnetDevice(device);
    setTerminalHistory([
      `Trying ${device.ip_address}...`,
      `Connected to ${device.ip_address}.`,
      `\nUser Access Verification\n\nUsername: admin\nPassword: ****\n\n${device.hostname}#`
    ]);
    setIsTelnetOpen(true);
  };

  const handleTelnetCommand = (e: React.FormEvent) => {
    e.preventDefault();
    if (!command.trim()) return;
    let output = ``;
    const cmd = command.toLowerCase();
    
    if (cmd === "show ip int brief" || cmd === "sh ip int br") {
      output = `Interface              IP-Address      OK? Method Status                Protocol\nGigabitEthernet0/1     ${telnetDevice.ip_address.padEnd(15)} YES manual up                    up\n`;
    } else if (cmd.startsWith("ping")) {
      output = `Sending 5, 100-byte ICMP Echos to ${telnetDevice.ip_address}:\n!!!!!\nSuccess rate is 100 percent (5/5)\n`;
    } else if (cmd === "show run" || cmd === "show running-config") {
      output = `Building configuration...\n!\nhostname ${telnetDevice.hostname}\n!\nend\n`;
    } else if (cmd === "exit" || cmd === "quit") {
      setIsTelnetOpen(false); return;
    } else {
      output = `% Invalid input detected at '^' marker.\n`;
    }
    setTerminalHistory(prev => [...prev, `${command}\n${output}\n${telnetDevice.hostname}#`]);
    setCommand("");
  };

  return (
    <div style={{ display: 'flex', height: '80vh', gap: '1rem' }}>
      
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <h1 style={{ marginBottom: '1rem', color: 'var(--accent-red)' }}>
          <AlertTriangle size={28} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '10px' }} /> 
          Action Center (Fault Fixing)
        </h1>

        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
          <button onClick={() => setTab("active")} style={{ padding: '0.5rem 1rem', borderRadius: '8px', border: 'none', cursor: 'pointer', background: tab === 'active' ? 'var(--accent-red)' : 'var(--bg-surface)', color: 'white', fontWeight: 600 }}>
            Active Faults ({downDevices.filter((d:any) => !d.is_maintenance).length})
          </button>
          <button onClick={() => setTab("maintenance")} style={{ padding: '0.5rem 1rem', borderRadius: '8px', border: 'none', cursor: 'pointer', background: tab === 'maintenance' ? 'var(--accent-amber)' : 'var(--bg-surface)', color: 'white', fontWeight: 600 }}>
            In Maintenance ({downDevices.filter((d:any) => d.is_maintenance).length})
          </button>
        </div>
        
        {isLoading ? <p>Loading faults...</p> : (
          <div className="data-card" style={{ padding: 0, overflow: 'hidden' }}>
            <table className="data-table">
              <thead>
                <tr><th>Station</th><th>Device (Click to View)</th><th>IP Address</th><th>Status</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {filteredDevices.length === 0 ? (
                  <tr>
                    <td colSpan={5} style={{ textAlign: 'center', padding: '2rem', color: tab === 'active' ? 'var(--accent-green)' : 'var(--text-muted)' }}>
                      {tab === 'active' ? <><CheckCircle size={24} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '8px' }}/> All devices are UP! 🎉</> : 'No devices in Maintenance.'}
                    </td>
                  </tr>
                ) : filteredDevices.map((d: any) => (
                  <tr key={d.device_id}>
                    <td style={{ fontWeight: 600 }}>{d.station_code}</td>
                    
                    <td>
                      <span 
                        onClick={() => navigate(`/device/${d.device_id}`)} 
                        style={{ color: 'var(--accent-blue)', cursor: 'pointer', textDecoration: 'underline', fontWeight: 600 }}
                      >
                        {d.hostname}
                      </span>
                      <span className={`badge ${d.is_maintenance ? 'badge-warning' : 'badge-down'}`} style={{ marginLeft: '8px' }}>{d.category}</span>
                    </td>
                    
                    <td style={{ fontFamily: 'monospace' }}>{d.ip_address}</td>
                    <td style={{ color: d.is_maintenance ? 'var(--accent-amber)' : 'var(--accent-red)' }}>{d.is_maintenance ? 'Maintenance' : 'Down'}</td>
                    
                    <td style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                      {!d.is_maintenance ? (
                        <>
                          <button onClick={() => handleAction(d.device_id, "PING", d.hostname)} className="btn" style={{ width: 'auto', padding: '0.3rem 0.6rem', background: 'var(--accent-blue)', fontSize: '0.8rem' }} title="Ping Device"><Activity size={14}/> Ping</button>
                          <button onClick={() => handleTelnetOpen(d)} className="btn" style={{ width: 'auto', padding: '0.3rem 0.6rem', background: '#475569', fontSize: '0.8rem' }} title="Telnet / SSH"><Terminal size={14}/> CLI</button>
                          <button onClick={() => handleAction(d.device_id, "RESTART_PORT", d.hostname)} className="btn" style={{ width: 'auto', padding: '0.3rem 0.6rem', background: 'var(--accent-amber)', fontSize: '0.8rem' }} title="Restart Port"><RotateCcw size={14}/> Restart</button>
                          <button onClick={() => handleAction(d.device_id, "REBOOT", d.hostname)} className="btn btn-danger" style={{ width: 'auto', padding: '0.3rem 0.6rem', fontSize: '0.8rem' }} title="Reboot"><Power size={14}/> Reboot</button>
                          <button onClick={() => maintenanceMutation.mutate({ id: d.device_id, status: true })} className="btn" style={{ width: 'auto', padding: '0.3rem 0.6rem', background: '#64748b', fontSize: '0.8rem' }} title="Set Maintenance"><Wrench size={14}/> Maint</button>
                        </>
                      ) : (
                        <button onClick={() => maintenanceMutation.mutate({ id: d.device_id, status: false })} className="btn" style={{ width: 'auto', padding: '0.3rem 0.6rem', background: 'var(--accent-green)', fontSize: '0.8rem' }}><CheckCircle size={14}/> Exit Maint</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Right Side: Output Terminal */}
      {terminalOutput && (
        <div style={{ width: '400px', background: '#000', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', borderBottom: '1px solid #333', paddingBottom: '0.5rem' }}>
            <span style={{ color: '#fff', fontFamily: 'monospace', fontSize: '0.9rem' }}><Terminal size={14} style={{ display: 'inline', marginRight: '6px' }}/> Output</span>
            <button onClick={() => setTerminalOutput(null)} style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer' }}>✕</button>
          </div>
          <pre style={{ color: '#10b981', fontFamily: 'monospace', fontSize: '0.85rem', whiteSpace: 'pre-wrap', flex: 1, overflowY: 'auto' }}>{terminalOutput}</pre>
        </div>
      )}

      {/* Modals... (Same as before) */}
      {confirmStep > 0 && targetAction && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.85)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 9999 }}>
          <div className="data-card" style={{ width: '500px', border: '3px solid var(--accent-red)', textAlign: 'center', padding: '2rem' }}>
            {confirmStep === 1 && (
              <>
                <ShieldAlert size={64} color="var(--accent-red)" style={{ margin: '0 auto 1rem' }} />
                <h2 style={{ color: 'var(--accent-red)', marginBottom: '1rem', fontSize: '1.5rem' }}>⚠️ खतरनाक कार्य</h2>
                <p style={{ fontSize: '1.1rem', marginBottom: '1.5rem' }}>क्या आप वाकई <strong>{targetAction.hostname}</strong> पर <strong>{targetAction.type === "REBOOT" ? "रिबूट" : "पोर्ट रीस्टार्ट"}</strong> करना चाहते हैं?</p>
                <div style={{ display: 'flex', gap: '1rem' }}>
                  <button className="btn" style={{ background: 'var(--bg-base)', border: '1px solid var(--border-color)' }} onClick={cancelConfirmation}>❌ रद्द करें</button>
                  <button className="btn btn-danger" onClick={nextConfirmStep}>हाँ, आगे बढ़ें →</button>
                </div>
              </>
            )}
            {confirmStep === 2 && (
              <>
                <Lock size={64} color="var(--accent-amber)" style={{ margin: '0 auto 1rem' }} />
                <h2 style={{ color: 'var(--accent-amber)', marginBottom: '1rem', fontSize: '1.5rem' }}>🔒 सत्यापन आवश्यक</h2>
                <p style={{ marginBottom: '1rem' }}>पुष्टि करने के लिए <strong>CONFIRM</strong> टाइप करें:</p>
                <input type="text" value={confirmText} onChange={e => setConfirmText(e.target.value)} autoFocus style={{ width: '100%', padding: '0.75rem', textAlign: 'center', border: '2px solid var(--accent-amber)', borderRadius: '6px', fontSize: '1.2rem', marginBottom: '1.5rem' }} />
                <div style={{ display: 'flex', gap: '1rem' }}>
                  <button className="btn" style={{ background: 'var(--bg-base)', border: '1px solid var(--border-color)' }} onClick={cancelConfirmation}>❌ रद्द करें</button>
                  <button className="btn" style={{ background: confirmText.toUpperCase() === 'CONFIRM' ? 'var(--accent-amber)' : 'var(--text-muted)' }} onClick={nextConfirmStep}>आगे बढ़ें →</button>
                </div>
              </>
            )}
            {confirmStep === 3 && (
              <>
                <Ban size={64} color="var(--accent-red)" style={{ margin: '0 auto 1rem' }} />
                <h2 style={{ color: 'var(--accent-red)', marginBottom: '1rem', fontSize: '1.5rem' }}>🚨 अंतिम चेतावनी</h2>
                <p style={{ fontSize: '1.1rem', marginBottom: '2rem' }}>इस कार्य से पूरा स्टेशन नेटवर्क कुछ समय के लिए ठप हो सकता है। क्या आप आश्वस्त हैं?</p>
                <div style={{ display: 'flex', gap: '1rem' }}>
                  <button className="btn" style={{ background: 'var(--bg-base)', border: '1px solid var(--border-color)' }} onClick={cancelConfirmation}>❌ रद्द करें</button>
                  <button className="btn btn-danger" onClick={nextConfirmStep}>✓ हाँ, निष्पादित करें</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Telnet Web Terminal */}
      {isTelnetOpen && telnetDevice && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.95)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 10000 }}>
          <div style={{ width: '850px', height: '550px', background: '#000', borderRadius: '8px', border: '2px solid #333', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div style={{ background: '#1e293b', padding: '0.75rem 1rem', display: 'flex', justifyContent: 'space-between', color: 'white' }}>
              <span>SSH: {telnetDevice.hostname}</span>
              <button onClick={() => setIsTelnetOpen(false)} style={{ background: 'transparent', border: 'none', color: 'var(--accent-red)', cursor: 'pointer' }}><X size={20}/></button>
            </div>
            <div style={{ flex: 1, padding: '1rem', overflowY: 'auto', color: '#10b981', fontFamily: 'monospace' }}>
              {terminalHistory.map((line, i) => <div key={i} style={{ whiteSpace: 'pre-wrap' }}>{line}</div>)}
              <div ref={terminalEndRef} />
            </div>
            <form onSubmit={handleTelnetCommand} style={{ display: 'flex', borderTop: '1px solid #333' }}>
              <span style={{ padding: '1rem', color: '#10b981' }}>{telnetDevice.hostname}#</span>
              <input type="text" value={command} onChange={e => setCommand(e.target.value)} autoFocus style={{ flex: 1, background: 'transparent', border: 'none', color: '#fff', padding: '1rem' }} />
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
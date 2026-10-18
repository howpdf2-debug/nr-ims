import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { 
  Server, Activity, RotateCcw, Power, Terminal, 
  AlertTriangle, CheckCircle, ShieldAlert, X, Lock, Ban
} from "lucide-react";

export default function ActionCenter() {
  const queryClient = useQueryClient();
  
  // Terminal Output State (Ping, CLI etc)
  const [terminalOutput, setTerminalOutput] = useState<string | null>(null);
  
  // Telnet Modal State
  const [isTelnetOpen, setIsTelnetOpen] = useState(false);
  const [telnetDevice, setTelnetDevice] = useState<any>(null);
  const [command, setCommand] = useState("");
  const [terminalHistory, setTerminalHistory] = useState<string[]>([]);
  const terminalEndRef = useRef<HTMLDivElement>(null);

  // Triple Confirmation State
  const [confirmStep, setConfirmStep] = useState(0); // 0=None, 1=Hindi Warn, 2=Type CONFIRM, 3=Final Warn
  const [targetAction, setTargetAction] = useState<{ id: string, type: string, hostname: string } | null>(null);
  const [confirmText, setConfirmText] = useState("");

  // API: Fetch Down Devices
  const { data: downDevices = [], isLoading } = useQuery({
    queryKey: ["downDevices"],
    queryFn: () => api.get("/actions/down-devices").then(res => res.data),
    refetchInterval: 10000, // हर 10 सेकंड में रिफ्रेश
  });

  // API: Execute Action
  const actionMutation = useMutation({
    mutationFn: (data: { device_id: string, action_type: string }) => api.post("/actions/execute", data),
    onSuccess: (res) => {
      setTerminalOutput(res.data.output);
      queryClient.invalidateQueries({ queryKey: ["downDevices"] });
      // अगर Reboot/Restart था, तो टर्मिनल क्लोज करें
      setTargetAction(null);
    },
    onError: () => alert("Action Failed! Please check backend.")
  });

  // Scroll terminal to bottom
  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [terminalHistory]);

  // --- ACTION HANDLER (Ping is safe, Restart/Reboot need 3-step) ---
  const handleAction = (id: string, type: string, hostname: string) => {
    if (type === "PING") {
      // Ping: Safe action, no confirmation needed
      setTerminalOutput(`Pinging ${hostname}...\nPlease wait...`);
      actionMutation.mutate({ device_id: id, action_type: type });
    } else {
      // Restart/Reboot: Start Triple Confirmation
      setTargetAction({ id, type, hostname });
      setConfirmStep(1);
    }
  };

  // --- TRIPLE CONFIRMATION LOGIC ---
  const nextConfirmStep = () => {
    if (confirmStep === 1) {
      // Step 1 -> Step 2
      setConfirmStep(2);
    } else if (confirmStep === 2) {
      // Step 2 -> Step 3 (only if CONFIRM typed)
      if (confirmText.toUpperCase() === "CONFIRM") {
        setConfirmStep(3);
      } else {
        alert("कृपया 'CONFIRM' शब्द सही से टाइप करें।\n(Please type CONFIRM correctly)");
      }
    } else if (confirmStep === 3 && targetAction) {
      // Step 3 -> Execute
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

  // --- TELNET / CLI HANDLER ---
  const handleTelnetOpen = (device: any) => {
    setTelnetDevice(device);
    setTerminalHistory([
      `Trying ${device.ip_address}...`,
      `Connected to ${device.ip_address}.`,
      `Escape character is '^]'.`,
      `\nUser Access Verification\n\nUsername: admin\nPassword: ****\n\n${device.hostname}#`
    ]);
    setIsTelnetOpen(true);
  };

  const handleTelnetCommand = (e: React.FormEvent) => {
    e.preventDefault();
    if (!command.trim()) return;
    
    let output = ``;
    const cmd = command.toLowerCase();
    
    // Router Command Simulation
    if (cmd === "show ip int brief" || cmd === "sh ip int br") {
      output = `Interface              IP-Address      OK? Method Status                Protocol\nGigabitEthernet0/0     unassigned      YES unset  administratively down down    \nGigabitEthernet0/1     ${telnetDevice.ip_address.padEnd(15)} YES manual up                    up\n`;
    } else if (cmd.startsWith("ping")) {
      output = `Type escape sequence to abort.\nSending 5, 100-byte ICMP Echos to ${telnetDevice.ip_address}, timeout is 2 seconds:\n!!!!!\nSuccess rate is 100 percent (5/5), round-trip min/avg/max = 1/1/1 ms\n`;
    } else if (cmd === "show run" || cmd === "show running-config") {
      output = `Building configuration...\n\nCurrent configuration : 1520 bytes\n!\nversion 15.2\nservice timestamps debug datetime msec\n!\nhostname ${telnetDevice.hostname}\n!\ninterface GigabitEthernet0/1\n ip address ${telnetDevice.ip_address} 255.255.255.0\n no shutdown\n!\nline vty 0 4\n password cisco\n login\n!\nend\n`;
    } else if (cmd === "exit" || cmd === "quit" || cmd === "logout") {
      setIsTelnetOpen(false);
      return;
    } else {
      output = `% Invalid input detected at '^' marker.\n`;
    }
    
    setTerminalHistory(prev => [...prev, `${command}\n${output}\n${telnetDevice.hostname}#`]);
    setCommand("");
  };

  return (
    <div style={{ display: 'flex', height: '80vh', gap: '1rem' }}>
      
      {/* ============ LEFT SIDE: DOWN DEVICES LIST ============ */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        
        <h1 style={{ marginBottom: '1.5rem', color: 'var(--accent-red)' }}>
          <AlertTriangle size={28} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '10px' }} /> 
          Action Center (Fault Fixing)
        </h1>
        
        {isLoading ? <p>Loading faults...</p> : (
          <div className="data-card" style={{ padding: 0, overflow: 'hidden' }}>
            <table className="data-table">
              <thead>
                <tr><th>Station</th><th>Device</th><th>IP Address</th><th>Issue</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {downDevices.length === 0 ? (
                  <tr>
                    <td colSpan={5} style={{ textAlign: 'center', padding: '2rem', color: 'var(--accent-green)' }}>
                      <CheckCircle size={24} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '8px' }}/> 
                      All devices are UP! 🎉
                    </td>
                  </tr>
                ) : downDevices.map((d: any) => (
                  <tr key={d.device_id}>
                    <td style={{ fontWeight: 600 }}>{d.station_code}</td>
                    <td>{d.hostname} <span className="badge badge-down">{d.category}</span></td>
                    <td style={{ fontFamily: 'monospace' }}>{d.ip_address}</td>
                    <td style={{ color: 'var(--accent-red)' }}>Unreachable</td>
                    <td style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                      <button onClick={() => handleAction(d.device_id, "PING", d.hostname)} className="btn" style={{ width: 'auto', padding: '0.3rem 0.6rem', background: 'var(--accent-blue)', fontSize: '0.8rem' }} title="Ping Device"><Activity size={14}/> Ping</button>
                      <button onClick={() => handleTelnetOpen(d)} className="btn" style={{ width: 'auto', padding: '0.3rem 0.6rem', background: '#475569', fontSize: '0.8rem' }} title="Telnet / SSH"><Terminal size={14}/> CLI</button>
                      <button onClick={() => handleAction(d.device_id, "RESTART_PORT", d.hostname)} className="btn" style={{ width: 'auto', padding: '0.3rem 0.6rem', background: 'var(--accent-amber)', fontSize: '0.8rem' }} title="Restart Port"><RotateCcw size={14}/> Restart</button>
                      <button onClick={() => handleAction(d.device_id, "REBOOT", d.hostname)} className="btn btn-danger" style={{ width: 'auto', padding: '0.3rem 0.6rem', fontSize: '0.8rem' }} title="Reboot"><Power size={14}/> Reboot</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ============ RIGHT SIDE: OUTPUT TERMINAL ============ */}
      {terminalOutput && (
        <div style={{ width: '400px', background: '#000', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', borderBottom: '1px solid #333', paddingBottom: '0.5rem' }}>
            <span style={{ color: '#fff', fontFamily: 'monospace', fontSize: '0.9rem' }}>
              <Terminal size={14} style={{ display: 'inline', marginRight: '6px' }}/> Command Output
            </span>
            <button onClick={() => setTerminalOutput(null)} style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer' }}>✕</button>
          </div>
          <pre style={{ color: '#10b981', fontFamily: 'monospace', fontSize: '0.85rem', whiteSpace: 'pre-wrap', flex: 1, overflowY: 'auto' }}>
            {terminalOutput}
          </pre>
        </div>
      )}

      {/* ============ TRIPLE CONFIRMATION MODALS ============ */}
      {confirmStep > 0 && targetAction && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.85)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 9999 }}>
          <div className="data-card" style={{ width: '500px', border: '3px solid var(--accent-red)', textAlign: 'center', padding: '2rem' }}>
            
            {/* --- STEP 1: Initial Hindi Warning --- */}
            {confirmStep === 1 && (
              <>
                <ShieldAlert size={64} color="var(--accent-red)" style={{ margin: '0 auto 1rem' }} />
                <h2 style={{ color: 'var(--accent-red)', marginBottom: '1rem', fontSize: '1.5rem' }}>
                  ⚠️ खतरनाक कार्य (Dangerous Action)
                </h2>
                <p style={{ fontSize: '1.1rem', marginBottom: '0.5rem', lineHeight: '1.6' }}>
                  क्या आप वाकई <strong style={{ color: 'var(--accent-amber)' }}>{targetAction.hostname}</strong> पर
                </p>
                <p style={{ fontSize: '1.3rem', marginBottom: '1.5rem', color: 'var(--accent-red)', fontWeight: 'bold' }}>
                  {targetAction.type === "REBOOT" ? "रिबूट (Reboot)" : "पोर्ट रीस्टार्ट (Restart)"}
                </p>
                <p style={{ fontSize: '1rem', marginBottom: '2rem' }}>
                  करना चाहते हैं?
                </p>
                <div style={{ display: 'flex', gap: '1rem' }}>
                  <button className="btn" style={{ background: 'var(--bg-base)', border: '1px solid var(--border-color)' }} onClick={cancelConfirmation}>
                    ❌ रद्द करें (Cancel)
                  </button>
                  <button className="btn btn-danger" onClick={nextConfirmStep}>
                    हाँ, आगे बढ़ें (Next) →
                  </button>
                </div>
              </>
            )}

            {/* --- STEP 2: Type CONFIRM --- */}
            {confirmStep === 2 && (
              <>
                <Lock size={64} color="var(--accent-amber)" style={{ margin: '0 auto 1rem' }} />
                <h2 style={{ color: 'var(--accent-amber)', marginBottom: '1rem', fontSize: '1.5rem' }}>
                  🔒 सत्यापन आवश्यक (Verification Required)
                </h2>
                <p style={{ marginBottom: '1rem', fontSize: '1.1rem' }}>
                  पुष्टि करने के लिए नीचे <strong style={{ color: 'var(--accent-red)' }}>CONFIRM</strong> टाइप करें:
                </p>
                <input 
                  type="text" 
                  value={confirmText} 
                  onChange={e => setConfirmText(e.target.value)} 
                  placeholder="यहाँ CONFIRM लिखें"
                  autoFocus
                  style={{ 
                    width: '100%', padding: '0.75rem', textAlign: 'center', 
                    background: 'var(--bg-base)', color: 'white', 
                    border: '2px solid var(--accent-amber)', borderRadius: '6px', 
                    fontSize: '1.3rem', letterSpacing: '3px', marginBottom: '1.5rem',
                    fontFamily: 'monospace'
                  }}
                />
                <div style={{ display: 'flex', gap: '1rem' }}>
                  <button className="btn" style={{ background: 'var(--bg-base)', border: '1px solid var(--border-color)' }} onClick={cancelConfirmation}>
                    ❌ रद्द करें
                  </button>
                  <button 
                    className="btn" 
                    style={{ background: confirmText.toUpperCase() === 'CONFIRM' ? 'var(--accent-amber)' : 'var(--text-muted)', cursor: confirmText.toUpperCase() === 'CONFIRM' ? 'pointer' : 'not-allowed' }} 
                    onClick={nextConfirmStep}
                  >
                    आगे बढ़ें →
                  </button>
                </div>
              </>
            )}

            {/* --- STEP 3: Final Warning --- */}
            {confirmStep === 3 && (
              <>
                <Ban size={64} color="var(--accent-red)" style={{ margin: '0 auto 1rem' }} />
                <h2 style={{ color: 'var(--accent-red)', marginBottom: '1rem', fontSize: '1.5rem' }}>
                  🚨 अंतिम चेतावनी (Final Warning)
                </h2>
                <div style={{ background: 'rgba(239, 68, 68, 0.1)', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', border: '1px solid var(--accent-red)' }}>
                  <p style={{ fontSize: '1.1rem', color: 'var(--accent-red)', fontWeight: 'bold', marginBottom: '0.5rem' }}>
                    चेतावनी: इस कार्य से पूरा स्टेशन नेटवर्क कुछ समय के लिए ठप हो सकता है।
                  </p>
                  <p style={{ fontSize: '0.95rem', color: 'var(--text-muted)' }}>
                    (Warning: This action may temporarily disrupt the entire station network.)
                  </p>
                </div>
                <p style={{ fontSize: '1.1rem', marginBottom: '2rem' }}>
                  क्या आप पूरी तरह आश्वस्त हैं?
                </p>
                <div style={{ display: 'flex', gap: '1rem' }}>
                  <button className="btn" style={{ background: 'var(--bg-base)', border: '1px solid var(--border-color)' }} onClick={cancelConfirmation}>
                    ❌ रद्द करें (Cancel)
                  </button>
                  <button className="btn btn-danger" onClick={nextConfirmStep}>
                    ✓ हाँ, निष्पादित करें (Execute)
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ============ TELNET WEB TERMINAL ============ */}
      {isTelnetOpen && telnetDevice && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.95)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 10000 }}>
          <div style={{ width: '850px', height: '550px', background: '#000', borderRadius: '8px', border: '2px solid #333', display: 'flex', flexDirection: 'column', overflow: 'hidden', boxShadow: '0 0 30px rgba(16, 185, 129, 0.2)' }}>
            
            {/* Terminal Header */}
            <div style={{ background: '#1e293b', padding: '0.75rem 1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'white', fontFamily: 'monospace' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Terminal size={18} />
                <span>SSH Session: {telnetDevice.hostname} ({telnetDevice.ip_address})</span>
              </div>
              <button onClick={() => setIsTelnetOpen(false)} style={{ background: 'transparent', border: 'none', color: 'var(--accent-red)', cursor: 'pointer' }}>
                <X size={20}/>
              </button>
            </div>
            
            {/* Terminal Body */}
            <div style={{ flex: 1, padding: '1rem', overflowY: 'auto', color: '#10b981', fontFamily: 'monospace', fontSize: '0.9rem', lineHeight: '1.5' }}>
              {terminalHistory.map((line, i) => (
                <div key={i} style={{ whiteSpace: 'pre-wrap' }}>{line}</div>
              ))}
              <div ref={terminalEndRef} />
            </div>
            
            {/* Terminal Input */}
            <form onSubmit={handleTelnetCommand} style={{ display: 'flex', borderTop: '1px solid #333', background: '#0a0a0a' }}>
              <span style={{ padding: '1rem 0 1rem 1rem', color: '#10b981', fontFamily: 'monospace' }}>{telnetDevice.hostname}#</span>
              <input 
                type="text" 
                value={command} 
                onChange={e => setCommand(e.target.value)} 
                placeholder="Type commands here (show ip int brief, ping, exit)..." 
                autoFocus
                style={{ flex: 1, background: 'transparent', border: 'none', color: '#fff', padding: '1rem', fontFamily: 'monospace', outline: 'none' }}
              />
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
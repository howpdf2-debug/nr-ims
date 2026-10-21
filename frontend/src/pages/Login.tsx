import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldAlert } from "lucide-react";
import { api, errorMessage } from "../lib/api";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    try {
      const formData = new URLSearchParams();
      formData.append("username", email);
      formData.append("password", password);
      const res = await api.post("/auth/login", formData, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" }
      });
      localStorage.setItem("token", res.data.access_token);
      navigate("/dashboard");
    } catch (err: unknown) {
      setError(errorMessage(err, "Login failed."));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '2rem', color: 'var(--accent-blue)' }}>
          <ShieldAlert size={48} />
        </div>
        <h2 style={{ textAlign: 'center', color: 'white', marginBottom: '2rem', fontSize: '1.5rem' }}>NOC Secure Login</h2>
        {error && <div className="error-msg">{error}</div>}
        <form onSubmit={handleLogin}>
          <div className="input-group">
            <label htmlFor="login-email">Email Address</label>
            <input id="login-email" type="text" name="email" autoComplete="username" autoFocus value={email} onChange={e => setEmail(e.target.value)} required />
          </div>
          <div className="input-group">
            <label htmlFor="login-password">Password</label>
            <input id="login-password" type="password" name="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required />
          </div>
          <button type="submit" className="btn" disabled={isLoading}>
            {isLoading ? "Authenticating..." : "Secure Login"}
          </button>
        </form>
      </div>
    </div>
  );
}

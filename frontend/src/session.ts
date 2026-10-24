// Sessão JWT e gerenciamento de contas no localStorage.
// Usuários e credenciais são salvos localmente no navegador (localStorage).
// O token JWT assinado é usado para autenticar as requisições à API.

export type SessaoUsuario = { id: number; nome: string; email: string };
export type Sessao = { token: string; user: SessaoUsuario };
export type UsuarioConta = { id: number; nome: string; email: string; senha: string };

const CHAVE_SESSAO = 'atlas-sessao';
const CHAVE_CONTAS = 'atlas-contas';

export function lerSessao(): Sessao | null {
  try {
    const raw = localStorage.getItem(CHAVE_SESSAO);
    if (!raw) return null;
    const sessao = JSON.parse(raw) as Partial<Sessao>;
    if (typeof sessao.token !== 'string' || typeof sessao.user !== 'object' || !sessao.user) return null;
    return sessao as Sessao;
  } catch {
    return null;
  }
}

export function guardarSessao(sessao: Sessao): void {
  try {
    localStorage.setItem(CHAVE_SESSAO, JSON.stringify(sessao));
  } catch {
    /* navegador sem storage: segue só em memória */
  }
}

export function limparSessao(): void {
  try {
    localStorage.removeItem(CHAVE_SESSAO);
  } catch {
    /* sem storage: nada a limpar */
  }
}

/** Cabeçalho Bearer para os fetches da API (vazio sem login). */
export function authHeaders(): Record<string, string> {
  const sessao = lerSessao();
  return sessao ? { Authorization: `Bearer ${sessao.token}` } : {};
}

export function lerContasLocais(): UsuarioConta[] {
  try {
    const raw = localStorage.getItem(CHAVE_CONTAS);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function cadastrarContaLocal(nome: string, email: string, senha: string): SessaoUsuario {
  const emailNorm = email.trim().toLowerCase();
  const contas = lerContasLocais();
  if (contas.some((c) => c.email.toLowerCase() === emailNorm)) {
    throw new Error('e-mail já cadastrado');
  }
  const novaConta: UsuarioConta = {
    id: Date.now(),
    nome: nome.trim(),
    email: emailNorm,
    senha,
  };
  contas.push(novaConta);
  try {
    localStorage.setItem(CHAVE_CONTAS, JSON.stringify(contas));
  } catch {
    /* sem storage */
  }
  return { id: novaConta.id, nome: novaConta.nome, email: novaConta.email };
}

export function autenticarContaLocal(email: string, senha: string): SessaoUsuario {
  const emailNorm = email.trim().toLowerCase();
  const contas = lerContasLocais();
  const conta = contas.find((c) => c.email.toLowerCase() === emailNorm && c.senha === senha);
  if (!conta) {
    throw new Error('e-mail ou senha inválidos');
  }
  return { id: conta.id, nome: conta.nome, email: conta.email };
}

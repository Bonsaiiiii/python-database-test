'''
# server.py
import asyncio, json

async def handle(reader, writer):
    try:
        data = await reader.read(1024)  # ler requisição
        print(data.decode())

        mensagem = json.dumps({
            "status": "sucesso",
            "mensagem": "Mensagem enviada com sucesso!"
        })
        resposta = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json; charset=utf-8\r\n"
            f"Content-Length: {len(mensagem.encode('utf-8'))}\r\n"
            "Connection: close\r\n"
            "\r\n"
            + mensagem
        )

        writer.write(resposta.encode('utf-8'))
        await writer.drain()
    except Exception as e:
        print("Erro:", e)
    finally:
        writer.close()
        await writer.wait_closed()

async def main():
    server = await asyncio.start_server(handle, '0.0.0.0', 5000)
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())

'''
import asyncio # responsável pelas funções assíncronas
import json # responsável por lidar com jsons
import requests # reponsável pela comunicação e requests
import psycopg2 # comunicação com o banco de dados
import re # valida expressões regulares ('busca')
import os # comandos
from datetime import datetime, timedelta # pega datas e horários
from collections import defaultdict
import time
import jwt

def gerar_embed_metabase(secret_key, question_id, parametros=None, exp_minutos=15):    
    payload = {
        "resource": {"question": question_id},
        "params": parametros or {},
        "exp": datetime.utcnow() + timedelta(minutes=exp_minutos)
    }

    token = jwt.encode(payload, secret_key, algorithm="HS256")
    url = f"http://192.168.15.16:3000/embed/question/{token}#bordered=true&titled=true"
    return url

#DELIMITER = '"apikey":"7B815B0F416B-47B7-8787-595B29F68791"}'

async def processar_dados_http(dados): # Função assíncrona para processar os dados HTTP
    try:
        cabecalho, corpo = dados.decode("utf-8").split("\r\n\r\n", 1)
    except ValueError:
        return None, "Erro ao separar cabeçalho e corpo."

    try:
        corpo_json = json.loads(corpo)
    except json.JSONDecodeError as e:
        return None, f"Erro ao processar o JSON: {str(e)}"

    if "event" in corpo_json and "data" in corpo_json:
        return corpo_json, None
    else:
        if "mac_addr" in corpo_json and "pasw" in corpo_json:
            return corpo_json, None
        else:
            return None, "Estrutura do JSON inválida. Falta 'event' ou 'data'."

def adicionar_spammer(cur, conn, nome, numero, motivo):
    if motivo == 1:
        motivo_lista = "SPAM"
    elif motivo == 2:
        motivo_lista = "LONGO"
    try:
        cur.execute("INSERT INTO spammer_list (pushname, number, motivo) VALUES(%s, %s, %s);",
        (nome, numero, motivo_lista))
        conn.commit()
    except psycopg2.IntegrityError as e:
        print(f"erro ao adicionar spammer: {e}")

def normalizar_numero(numero: str) -> str: # tenta fazer uma formatação básica do número
    numero = re.sub(r'[^\d+]', '', numero)
    
    if numero.startswith('+55'):
        return numero
    elif len(numero) == 11:
        return '+55' + numero
    elif len(numero) == 13 and numero.startswith('55'):
        return '+' + numero
    else:
        return numero

# Estrutura global para rastrear mensagens por número
limite_mensagens = defaultdict(list)

# Limite de 5 mensagens a cada 60 segundos por número
MAX_MENSAGENS = 5
PERIODO = 60

def is_spammer(numero):
    agora = time.time()
    timestamps = limite_mensagens[numero]

    # Remove timestamps mais antigos que o período
    limite_mensagens[numero] = [t for t in timestamps if agora - t < PERIODO]

    if len(limite_mensagens[numero]) >= MAX_MENSAGENS:
        return True

    limite_mensagens[numero].append(agora)
    return False

def enviar_mensagem(number, text, tipo = 0): # Função para enviar a mensagem para o número via API externa
    if tipo == 0:
        url = "http://localhost:8080/message/sendText/zap%20doido"
        payload = {
            "number": number,
            "text": text
        }
    elif tipo == 1: 
        url = "http://localhost:8080/message/sendMedia/zap%20doido"
        payload = {
            "number": number,
            "mediatype": "image",
            "mimetype": "image/png",
            "caption": "Codora",
            "media": "https://upload.wikimedia.org/wikipedia/commons/d/d8/Taoniscus.jpg",
            "fileName": "Codorna.png"
        }
    headers = {
        "Content-Type": "application/json",
        "apikey": "7B815B0F416B-47B7-8787-595B29F68791",
        "User-Agent": "PostmanRuntime/7.44.1",
        "Accept": "*/*"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        return response.status_code, response.text
    except requests.RequestException as e:
        return 500, str(e)

def handle_adm(conn, cur, mensagem, numero, mac): # lida com a comunicação do adm
    print("handle_adm")

    try:
        # adiciona usuário
        adicionar_user = re.search(
            r'adicionar usuário:\s*nome=(.*?),\s*n[úu]mero=([\d+]+),\s*ap=(\S+)',
            mensagem
        ) #desejo adicionar: nome=Ronaldo, número=11988887777, ap=102

        if adicionar_user:
            nome = adicionar_user.group(1).strip().title()
            numero_user = adicionar_user.group(2).strip()
            numero_user = normalizar_numero(numero_user)
            apartamento = adicionar_user.group(3).strip().upper()

            try:
                cur.execute("""
                    INSERT INTO user_maintable (mac, apartamento, name, number, is_admin)
                    VALUES (%s, %s, %s, %s, %s);
                """, (mac, apartamento, nome, numero_user, False))
                conn.commit()
                print("antes de enviar o bagulho")
                return enviar_mensagem(
                    numero, f"Usuário {nome} adicionado com sucesso!\nApartamento: {apartamento}\nNúmero: {numero_user}"
                )
                print("depois de enviar o bagulho")
            except psycopg2.IntegrityError as e:
                conn.rollback()
                print(f"Erro no banco: {e}")
                print(e)
                if 'new row for relation "user_maintable" violates check constraint "user_maintable_number_check"' in str(e):
                    return enviar_mensagem(
                        numero, f"Erro: o número não segue os padrões, tente +551199999999 (+55 48 9999 9999)"
                    )
                elif 'duplicate key value violates unique constraint "user_maintable_number_key"' in str(e): 
                    return enviar_mensagem(
                        numero, f"Erro: o número {numero_user} já está cadastrado."
                    )
                else:
                    print("else executado")
                    return enviar_mensagem(
                        numero, f"Erro: erro desconhecido"
                    )
        else:
            # Mensagem parece tentar adicionar, mas está mal formatada
            if "adicionar usuário" in mensagem:
                return enviar_mensagem(
                    numero,
                    "Formato inválido. Use assim:\n"
                    "adicionar usuário: nome=João, número=+551199999999, ap=101"
                )

        # remove usuário
        remover_user = re.search(
            r'remover usuário:\s*n[úu]mero=([\d+]+)',
            mensagem
        )

        if remover_user:
            numero_user = remover_user.group(1).strip()

            print(f"numero de remover user: {numero_user}")

            try: 
                cur.execute("""
                    DELETE from user_maintable where number = %s
                """, (numero_user,)) 
                conn.commit()
                return enviar_mensagem(
                    numero, f"sucesso ao remover o usuário de número: {numero_user}"
                )

            except psycopg2.IntegrityError as e:
                conn.rollback()
                print(f"Erro no banco: {e}")
                print(e)
        else:
            if "remover usuário" in mensagem:
                return enviar_mensagem(
                    numero,
                    "Formato inválido: Use assim:\n"
                    "remover usuário: número=+551199999999"
                )
        
        # mostra usuários cadastrados
        if mensagem.startswith('mostrar usuários'):
            try:
                cur.execute("""
                    SELECT name, number FROM user_maintable WHERE mac = %s
                """, (mac,))
                resultados = cur.fetchall()
                
                if resultados:
                    resposta = "Usuários registrados com este MAC:\n"
                    for nome, numeros in resultados:
                        resposta += f"- {nome}: {numeros}\n"
                    print(f"resposta strip: {resposta.strip()}")
                    return enviar_mensagem(numero, resposta.strip())
                else:
                    return enviar_mensagem(numero, "Nenhum usuário encontrado para este MAC.")
            
            except psycopg2.Error as e:
                conn.rollback()
                print(f"Erro no banco: {e}")
                return enviar_mensagem(numero, "Erro ao buscar os usuários.")

        else:
            return handle_usuario(conn, cur, mensagem, numero, 1)
    except Exception as e:
        print(f"excessão: {e}")

def handle_usuario(conn, cur, mensagem, numero, adm = 0): # definindo a função que lida com o usuário
    if mensagem == 'mostrar últimos dados':
        try:
            cur.execute("SELECT * FROM esp_medicoes ORDER BY data_hora DESC LIMIT 10;")
            conn.commit()
            dados = cur.fetchall()
            resultado = ""

            for linha in dados:
                # Supondo que sua tabela esp_medicoes tenha essas colunas:
                # id, esp_id, data_hora, agua_nivel, pressao, fluxo, fluxo_total, alerta
                resultado += (
                    f"Data: {linha[2]}\n"
                    f"Nível da água: {linha[3]}\n"
                    f"Pressão: {linha[4]}\n"
                    f"Fluxo: {linha[5]}\n"
                    f"Fluxo total: {linha[6]}\n"
                    f"Alerta: {linha[7]}\n\n"
                )

            return enviar_mensagem(numero, resultado.strip())
            #return enviar_mensagem(numero, "Opção 1 selecionada (agora faz nada kkkk SOBRA NAAAADA)")
        except psycopg2.IntegrityError as e:
            print(f"Erro de Integridade no Banco de dados: {e}")
            conn.rollback()
            return enviar_mensagem(remote_jid, "Erro desconhecido.")
        #try:
        #    cur.execute("INSERT INTO user_maintable (mac, apartamento, name, number, is_admin) VALUES(%s, %s, %s, %s, %s);",
        #                ('00:00:00:00:00:00', 'auguxxto', 'Ronaldo', '4991301010', False))
        #    conn.commit()
        #    status_code, response_text = enviar_mensagem(remote_jid, "Opção 1 selecionada e cadastro realizado.")
        #except psycopg2.IntegrityError as e:
        #    print(f"Erro de Integridade no Banco de dados: {e}")
        #    conn.rollback()
        #    status_code, response_text = enviar_mensagem(remote_jid, "Erro: você já está cadastrado.")

    elif mensagem == 'opção 2':
        return enviar_mensagem(numero, "Opção 2 selecionada", 1)

    elif mensagem == "ver dashboard":
            try:
                # gere o link
                url = gerar_embed_metabase(
                    secret_key="43226186ad57ace649cef4f5d5e10477dea19100dac18873a8fb2b36a370caad",  # Substitua pela real
                    question_id=39,                  # ID do seu dashboard
                )
                return enviar_mensagem(numero, url)
            except Exception as e:
                print(f"Erro ao gerar link Metabase: {e}")
                return enviar_mensagem(numero, "Erro ao gerar o link do Metabase.")

    elif mensagem == 'ajuda':
        if adm == 0:
            return enviar_mensagem(numero, "Olá 🐎🐎🐎 Buenas tardes!!!, Digite 'Mostrar últimos dados' para mostrar os últimos 10 dados da tabela\n"
            "'Opção 2' para ter uma surpresa calorosa\n"
            "'Ver dashboard' para receber o link para uma tabela mostrando a média dos dados.")
        else:
            return enviar_mensagem(numero, "Olá 🐎🐎🐎 ademiro 🐎🐎🐎 Buenas tardes!!!, lista de comandos de ademiro:\n"
            "Digite 'Mostrar últimos dados' para mostrar os últimos 10 dados da tabela\n"
            "'Opção 2' para ter uma surpresa calorosa\n"
            "'Ver dashboard' para receber o link para uma tabela mostrando a média dos dados.\n"
            "Digite 'Adicionar usuário' para isntruções de como adicionar um usuário\n"
            "Digite 'Remover usuário' para instruções de como remover usuário\n"
            "Digite 'Mostrar usuários' para mostrar os usuários cadastrados no seu dispositivo")

    else:
        return enviar_mensagem(numero, "Mensagem inválida. Escreva 'Ajuda' para ver a lista de comandos")

def handle_cadastro(conn, cur, mensagem, numero):
    try:
        cadastrar_user = re.search(
            r'logar em dispositivo:\s*mac=([0-9A-Fa-f:]{17}),\s*senha=(.*?),\s*nome=(.*?),\s*apartamento=(\S+)', 
            mensagem
        )

        if cadastrar_user:
            mac_user = cadastrar_user.group(1)
            senha_user = cadastrar_user.group(2)
            nome_user = cadastrar_user.group(3)
            apartamento_user = cadastrar_user.group(4)

            try:
                cur.execute("""
                    SELECT mac, password FROM esp_info WHERE mac = %s
                """, (mac_user,))
            
                resultado = cur.fetchone()

                if resultado:
                    mac_db, senha_db = resultado
                    if senha_user == senha_db:
                        print("Senha correta")
                        try:
                            cur.execute("""
                            INSERT INTO user_maintable(mac, apartamento, name, number, is_admin)
                            VALUES (%s, %s, %s, %s, true)
                            """, (
                                (mac_user, apartamento_user, nome_user, numero)
                            ))
                            conn.commit()
                        except psycopg2.IntegrityError as e:
                            conn.rollback()
                            print(f"Erro no banco: {e}")
                            print(e)

                        status_code, response_text = enviar_mensagem(numero, "deu certo")
                    else: 
                        status_code, response_text = enviar_mensagem(numero, "senha incorreta")
                        print("Senha incorreta")
                else: 
                    status_code, response_text = enviar_mensagem(numero, "mac não encontrado na rede")

            except psycopg2.IntegrityError as e:
                conn.rollback()
                print(f"Erro no banco: {e}")
                return enviar_mensagem(numero, "Não encontrado no banco de dados")
        elif mensagem == 'logar em dispositivo': 
            return enviar_mensagem(numero, "Mensagem incorreta, tente 'Logar em dispositivo: Mac=00:11:22:33:44:55, Senha=12345678', Nome=João, Apartamento=São Joaquim")
        else: 
            return enviar_mensagem(numero, "Bem-vindo ao serviço de monitoramento de caixa de água da HugenPLUS,"
                "caso queira se cadastrar insira conforme o exemplo utilizando as credenciais do seu despositivo:\n"
                "'Logar em dispositivo: Mac=00:11:22:33:44:55, Senha=12345678'")
    except Exception as e:
        print(f"Erro ocorrido: {e}")


async def handle_cliente(cliente_reader, cliente_writer): # Função assíncrona para lidar com a comunicação do cliente e ESP
    dados = b''
    resposta = ''  # Garantimos que `resposta` sempre exista

    try:
        #while True:
            #dados_str = await cliente_reader.read(4096)
            #if not dados_str:
            #    break
            #dados += dados_str

            #if DELIMITER in dados.decode("utf-8"):
            #    break

        while True:
            more = await cliente_reader.read(32600)
            if not more:
                break
            dados += more

            #if DELIMITER in dados.decode("utf-8"):
            #    break

            try:
                cabecalho, corpo = dados.decode().split("\r\n\r\n", 1)
            except ValueError:
                continue
            if corpo.strip():
                break

        if dados:
            print(f"Dados recebidos: {dados.decode('utf-8')}") # printa os dados
            print(f"Tamanho dos dados recebidos:{len(dados)}")
            corpo_json, erro = await processar_dados_http(dados)
            if erro:
                resposta = f"HTTP/1.1 400 Bad Request\r\nContent-Type: text/plain\r\n\r\n{erro}"
            else:
                try:
                    #conn = psycopg2.connect(
                    #    database=os.environ["DB_NAME"],
                    #    user=os.environ["DB_USER"],
                    #    host=os.environ["DB_HOST"],
                    #    password=os.environ["DB_PASSWORD"],
                    #    port=os.environ["DB_PORT"]
                    #)
                    conn = psycopg2.connect(
                        database="mydatabase",
                        user="myuser",
                        host="localhost",
                        password="mypassword",
                        port=5431
                    )
                    cur = conn.cursor()

                    sender = corpo_json["sender"]
                    print(f"sender: {sender}")
                    if sender == "esp_send":
                        mac_addr = corpo_json["mac_addr"]
                        pasw = corpo_json["pasw"]
                        esp_nivel = corpo_json["distancia"]
                        esp_fluxo = corpo_json ["fluxo_agua"]
                        esp_fluxo_total = corpo_json["fluxo_total"]
                        esp_pressao = corpo_json["pressao"]
                        print(f"endereço esp: {mac_addr}, senha: {pasw}, distancia do sensor: {esp_nivel}, fluxo de água: {esp_fluxo}, pressao da agua: {esp_pressao}")
                        #esp_nivel = corpo_json["esp_nivel"]
                        #esp_pressao = corpo_json["esp_pressao"]
                        #esp_vazao = corpo_json["esp_vazao"]
                        #esp_alerta = corpo_json["esp_alerta"]

                        cur.execute("""
                            SELECT mac, password, id FROM esp_info WHERE mac = %s
                        """, (mac_addr,))
                        esp_info = cur.fetchone()
                        esp_info_mac = esp_info[0]
                        
                        esp_info_pasw = esp_info[1]
                        esp_info_id = esp_info[2]
                        if mac_addr == esp_info_mac and pasw == esp_info_pasw:
                            print("esp encontrado no banco e senha correta, atualizando dados")
                            cur.execute("""
                                INSERT INTO esp_medicoes(esp_id, data_hora, agua_nivel, pressao, fluxo, fluxo_total, alerta)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (
                                esp_info_id,
                                datetime.now(),
                                esp_nivel, esp_pressao, esp_fluxo, esp_fluxo_total, 0
                            ))
                            conn.commit()
                            status_code = 200
                            response_text = "ESP OK"
                        else:
                            status_code = 403
                            response_text = "Credenciais do ESP inválidas"

                    else:
                        remote_jid = corpo_json["data"]["key"]["remoteJid"]
                        remote_jid_tratado = '+' + remote_jid.replace('@s.whatsapp.net', '')
                        conversation = corpo_json["data"]["message"]["conversation"]
                        conversation_lower = conversation.lower()
                        pushname = corpo_json["data"]["pushName"]

                        current_time = datetime.now()
                        print(f"remoteJid: {remote_jid}, conversation: {conversation}, hora: {current_time}")

                        if is_spammer(remote_jid_tratado):
                            print(f"Número {remote_jid_tratado} bloqueado temporariamente por spam.")
                            resposta = "HTTP/1.1 200 Too Many Requests\r\nContent-Type: text/plain\r\n\r\nVocê está enviando mensagens muito rápido. Tente novamente em breve."
                            cliente_writer.write(resposta.encode('utf-8'))
                            await cliente_writer.drain()
                            cliente_writer.close()
                            adicionar_spammer(cur, conn, pushname, remote_jid_tratado, 1)
                            return
                        if len(dados) > 16300:
                            print(f"Número {remote_jid_tratado} adicionado a lista de spam por ter mandado mensagem grande.")
                            adicionar_spammer(cur, conn, pushname, remote_jid_tratado, 2)

                        cur.execute("""
                            SELECT number, mac, is_admin FROM user_maintable WHERE number = %s
                        """, (remote_jid_tratado,))
                        print(f"remotejid: {remote_jid_tratado}")
                        numero = cur.fetchone()
                        print(f"numero aquii: {numero}")
                        if numero:
                            number = numero[0]
                            mac = numero[1]
                            is_admin = numero[2]

                            print(f"Número encontrado: {number}")
                            print(f"o mac é esse aqui: {mac}")
                            print(f"É admin: {is_admin}")

                            if is_admin:
                                print("O usuário é um administrador.")
                                #status_code, response_text = handle_usuario(conn, cur, conversation_lower, remote_jid)
                                status_code, response_text = handle_adm(conn, cur, conversation_lower, remote_jid, mac)
                                print(f"status code: {status_code}")
                                print(response_text)

                            else:
                                print("O usuário não é um administrador.")
                                status_code, response_text = handle_usuario(conn, cur, conversation_lower, remote_jid)
                        else:
                            handle_cadastro(conn, cur, conversation_lower, remote_jid_tratado)
                            print('Usuário não encontrado no banco de dados')

                    cur.close()
                    conn.close()

                    if status_code in (200, 201):
                        mensagem = json.dumps({"status":"sucesso","mensagem":"ok"})
                        resposta = (
                            "HTTP/1.1 200 OK\r\n"
                            "Content-Type: application/json; charset=utf-8\r\n"
                            f"Content-Length: {len(mensagem.encode('utf-8'))}\r\n"
                            "Connection: close\r\n"
                            "\r\n"
                            + mensagem
                        )
                    else:
                        print("status code erro ao enviar")
                        resposta = f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nErro ao enviar mensagem: {response_text}"

                except KeyError as e:
                    print(f"Erro ao acessar os dados: {e}")
                    status_code, response_text = enviar_mensagem(remote_jid, "Tipo de mensagem inválida")
                    resposta = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n"

    except Exception as e:
        print(f"Erro inesperado no servidor: {e}")
        resposta = f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nErro interno no servidor."

    finally:
        # Sempre envia resposta, mesmo em caso de erro
        if resposta:
            print(resposta)
        cliente_writer.write(resposta.encode('utf-8'))
        await cliente_writer.drain()
        cliente_writer.close()
        await cliente_writer.wait_closed()

# Função assíncrona para iniciar o servidor
async def iniciar_servidor(host, porta):
    servidor = await asyncio.start_server(handle_cliente, host, porta)
    addr = servidor.sockets[0].getsockname()
    print(f"Servidor ouvindo em {addr[0]}:{addr[1]}...")

    try:
        # Aguarda por novas conexões indefinidamente
        await servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")

# Inicia o servidor assíncrono
if __name__ == "__main__":
    host = '0.0.0.0'
    porta = 5000
    asyncio.run(iniciar_servidor(host, porta))
'''
    CREATE EXTENSION IF NOT EXISTS "pgcrypto";

    CREATE TABLE esp_info (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        mac TEXT UNIQUE NOT NULL CHECK(
        mac ~* '^([0-9A-F]{2}:){5}[0-9A-F]{2}$'
        ),
        password VARCHAR(255) NOT NULL,
        -- adicionar apartamento provavelmente
        --agua_nivel VARCHAR(5) NOT NULL,     
        --pressao VARCHAR(5) NOT NULL,
        --vazao VARCHAR(5) NOT NULL,
        --alerta VARCHAR(5) NOT NULL
    );

    CREATE TABLE esp_medicoes (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        esp_id UUID NOT NULL REFERENCES esp_info(id) ON DELETE CASCADE,
        data_hora TIMESTAMP NOT NULL DEFAULT NOW(),
        agua_nivel FLOAT NOT NULL,
        pressao FLOAT NOT NULL,
        fluxo FLOAT NOT NULL,
        fluxo_total FLOAT NOT NULL,
        alerta SMALLINT NOT NULL
    );

    CREATE TABLE user_maintable (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        mac TEXT NOT NULL,
        apartamento VARCHAR(100) NOT NULL, -- trocar por bloco (e/ ou ap) provavelmente
        name VARCHAR(100) NOT NULL,
        number VARCHAR(20) UNIQUE NOT NULL CHECK (
            number ~ '^\+55[1-9][0-9][0-9]{8}$' -- number ~ '^\+?[1-9][0-9]{1,14}$'
        ),
        is_admin BOOLEAN DEFAULT false,
        -- Definindo a chave estrangeira que faz referência ao campo 'mac' da tabela esp_info
        CONSTRAINT fk_mac FOREIGN KEY (mac) REFERENCES esp_info (mac) ON DELETE CASCADE ON UPDATE CASCADE
    );

    CREATE TABLE spammer_list (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        pushname VARCHAR(20),
        number VARCHAR(20) UNIQUE NOT NULL CHECK (
            number ~ '^\+55[1-9][0-9][0-9]{8}$' -- number ~ '^\+?[1-9][0-9]{1,14}$'
        ),
        motivo VARCHAR(10) UNIQUE NOT NULL
    );

    SELECT
        s.id,
        s.pushname,
        s.number,
        s.motivo,
        CASE
            WHEN u.number IS NOT NULL THEN 'sim'
            ELSE 'não'
        END AS eh_usuario
    FROM spammer_list s
    LEFT JOIN user_maintable u ON s.number = u.number;

    CREATE INDEX idx_esp_info_mac ON esp_info(mac);
    CREATE INDEX idx_user_maintable_number ON user_maintable(number);
    CREATE INDEX idx_spammer_list_number ON spammer_list(number);

    COMMENT ON TABLE esp_info IS 'Tabela com informações dos dispositivos (ESP) - Funciona como a tabela "principal"';
    COMMENT ON TABLE user_maintable IS 'Tabela principal de usuários e suas informações';
    COMMENT ON TABLE spammer_list IS 'Tabela que mostra números de usuários que tentaram serem sacaninhas';
'''
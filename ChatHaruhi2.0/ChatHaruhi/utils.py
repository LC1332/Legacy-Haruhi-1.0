from argparse import Namespace

import openai
from transformers import AutoModel, AutoTokenizer
import torch
import random

import tiktoken



device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

_luotuo_model = None

_enc_model = None

def tiktokenizer( text ):
    global _enc_model

    if _enc_model is None:
        _enc_model = tiktoken.get_encoding("cl100k_base")

    return len(_enc_model.encode(text))
    

def download_models():
    print("正在下载Luotuo-Bert")
    # Import our models. The package will take care of downloading the models automatically
    model_args = Namespace(do_mlm=None, pooler_type="cls", temp=0.05, mlp_only_train=False,
                           init_embeddings_model=None)
    model = AutoModel.from_pretrained("silk-road/luotuo-bert-medium", trust_remote_code=True, model_args=model_args).to(
        device)
    print("Luotuo-Bert下载完毕")
    return model

def get_luotuo_model():
    global _luotuo_model
    if _luotuo_model is None:
        _luotuo_model = download_models()
    return _luotuo_model


def luotuo_embedding(model, texts):
    # Tokenize the texts_source
    tokenizer = AutoTokenizer.from_pretrained("silk-road/luotuo-bert-medium")
    inputs = tokenizer(texts, padding=True, truncation=False, return_tensors="pt")
    inputs = inputs.to(device)
    # Extract the embeddings
    # Get the embeddings
    with torch.no_grad():
        embeddings = model(**inputs, output_hidden_states=True, return_dict=True, sent_emb=True).pooler_output
    return embeddings


def get_embedding_for_chinese(model, texts):
    model = model.to(device)
    # str or strList
    texts = texts if isinstance(texts, list) else [texts]
    # 截断
    for i in range(len(texts)):
        if len(texts[i]) > 510:
            texts[i] = texts[i][:510]
    if len(texts) >= 64:
        embeddings = []
        chunk_size = 64
        for i in range(0, len(texts), chunk_size):
            embeddings.append(luotuo_embedding(model, texts[i: i + chunk_size]))
        return torch.cat(embeddings, dim=0)
    else:
        return luotuo_embedding(model, texts)


def is_chinese_or_english(text):
    text = list(text)
    is_chinese, is_english = 0, 0

    for char in text:
        # 判断字符的Unicode值是否在中文字符的Unicode范围内
        if '\u4e00' <= char <= '\u9fa5':
            is_chinese += 4
        # 判断字符是否为英文字符（包括大小写字母和常见标点符号）
        elif ('\u0041' <= char <= '\u005a') or ('\u0061' <= char <= '\u007a'):
            is_english += 1
    if is_chinese >= is_english:
        return "chinese"
    else:
        return "english"


def get_embedding_for_english(text, model="text-embedding-ada-002"):
    text = text.replace("\n", " ")
    return openai.Embedding.create(input=[text], model=model)['data'][0]['embedding']

import os

def luotuo_openai_embedding(texts, is_chinese= None ):
    """
        when input is chinese, use luotuo_embedding
        when input is english, use openai_embedding
        texts can be a list or a string
        when texts is a list, return a list of embeddings, using batch inference
        when texts is a string, return a single embedding
    """

    openai_key = os.environ.get("OPENAI_API_KEY")

    if isinstance(texts, list):
        index = random.randint(0, len(texts) - 1)
        if openai_key is None or is_chinese_or_english(texts[index]) == "chinese":
            return [embed.cpu().tolist() for embed in get_embedding_for_chinese(get_luotuo_model(), texts)]
        else:
            return [get_embedding_for_english(text) for text in texts]
    else:
        if openai_key is None or is_chinese_or_english(texts) == "chinese":
            return get_embedding_for_chinese(get_luotuo_model(), texts)[0].cpu().tolist()
        else:
            return get_embedding_for_english(texts)


# compute cosine similarity between two vector
def get_cosine_similarity( v1, v2):
    v1 = torch.tensor(v1).to(device)
    v2 = torch.tensor(v2).to(device)
    return torch.cosine_similarity(v1, v2, dim=0).item()

    


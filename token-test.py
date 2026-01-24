import streamlit as st
import requests
import os
import certifi
import json

# Set up the page
st.set_page_config(page_title="Token Debugger", page_icon="🔑")

st.title("🔑 Shopify Access Token Debugger")

# 1. Inputs for Client ID and Secret
st.header("1. Input Credentials")

client_id_input = st.text_input("Client ID", value=os.getenv("SHOPIFY_CLIENT_ID", ""), type="password")
client_secret_input = st.text_input("Client Secret", value=os.getenv("SHOPIFY_CLIENT_SECRET", ""), type="password")
shop_url = "https://braless-butter.myshopify.com"

# 2. Prepare Request
st.header("2. Prepare Token Request")

if client_id_input and client_secret_input:
    token_url = f"{shop_url}/admin/oauth/access_token"
    payload = {
        "client_id": client_id_input,
        "client_secret": client_secret_input,
        "grant_type": "client_credentials"
    }

    st.markdown(f"**Target URL:** `{token_url}`")
    st.markdown("**Payload:**")
    st.json(payload)

    # 3. Request Access Token
    st.header("3. Request Access Token")

    if st.button("Get Access Token"):

        st.toast("Sending request to Shopify...", icon="🚀")

        try:
            response = requests.post(token_url, json=payload, verify=certifi.where())

            st.markdown("**Response Status Code:**")
            st.code(response.status_code)

            st.markdown("**Response Body:**")
            st.json(response.json())

            if response.status_code == 200:
                data = response.json()
                access_token = data.get("access_token")

                if access_token:
                    st.toast("Access token retrieved!", icon="✅")
                    st.success("Access token successfully retrieved.")
                    st.session_state['debug_access_token'] = access_token
                else:
                    st.toast("No access token in response.", icon="❌")
                    st.error("Response did not contain an access token.")
            else:
                st.toast(f"Request failed with status {response.status_code}", icon="❌")
                st.error("Failed to retrieve access token.")

        except Exception as e:
            st.toast(f"Exception occurred: {str(e)}", icon="🔥")
            st.error(f"An error occurred: {str(e)}")

# 4. Authenticated Request
st.header("4. Test Authenticated Query")

if 'debug_access_token' in st.session_state:
    access_token = st.session_state['debug_access_token']
    st.info(f"Using Access Token: `{access_token[:10]}...`")

    query = """{
      products(first: 5) {
        edges {
          node {
            id
            title
          }
        }
      }
    }"""

    st.markdown("**GraphQL Query:**")
    st.code(query, language="graphql")

    if st.button("Run Test Query"):
        st.toast("Running GraphQL query...", icon="🔎")

        graphql_url = f"{shop_url}/admin/api/2026-01/graphql.json"

        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token
        }

        data = {"query": query}

        try:
            response = requests.post(graphql_url, headers=headers, json=data)

            st.markdown("**Response Status Code:**")
            st.code(response.status_code)

            st.markdown("**Response Body:**")
            st.json(response.json())

            if response.status_code == 200:
                st.toast("Query executed successfully!", icon="✅")
                st.success("Query successful!")
            else:
                st.toast("Query failed.", icon="❌")
                st.error("Query failed.")

        except Exception as e:
            st.toast(f"Exception: {str(e)}", icon="🔥")
            st.error(f"An error occurred during query: {str(e)}")

else:
    st.warning("Get a valid access token in Step 3 first.")
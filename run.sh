PATH="$(pwd)/bunch_of_agents"
echo "Running agents from $PATH"

echo "Starting agents..."
# # read cookies straight from Brave (the default profile)
# /usr/local/Caskroom/miniforge/base/envs/rnd_env/bin/python $PATH/lxmls_agent.py --cookies-from-browser brave --download-sleep 6 #--dry-run

# # a specific Brave profile
# /usr/local/Caskroom/miniforge/base/envs/rnd_env/bin/python $PATH/khipu_agent.py --cookies-from-browser brave --download-sleep 6 # --browser-profile "Profile 1"

# # fallback: an exported cookies.txt
# /usr/local/Caskroom/miniforge/base/envs/rnd_env/bin/python $PATH/indaba_agent.py --cookies-from-browser brave --download-sleep 6 # --cookies ./cookies.txt

# slower and gentler downloads
/usr/local/Caskroom/miniforge/base/envs/rnd_env/bin/python $PATH/epfl_cs433_agent.py --cookies-from-browser brave --download-sleep 6 --dry-run

#!/bin/bash
# setup.sh - For Linux/Mac
echo "🚀 Setting up BankCat Demo..."

# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt

# Create .streamlit folder
mkdir -p .streamlit

# Create secrets template
if [ ! -f ".streamlit/secrets.toml" ]; then
    echo "# Add your database URL here" > .streamlit/secrets.toml
    echo "# DATABASE_URL = \"postgresql://username:password@host:port/database\"" >> .streamlit/secrets.toml
    echo "✅ Created .streamlit/secrets.toml"
else
    echo "✅ Secrets file already exists"
fi

echo ""
echo "✅ Setup complete!"
echo "📝 Next steps:"
echo "1. Edit .streamlit/secrets.toml with your database URL"
echo "2. Run: streamlit run app.py"
echo "3. Click 'Initialize Database' in Settings"

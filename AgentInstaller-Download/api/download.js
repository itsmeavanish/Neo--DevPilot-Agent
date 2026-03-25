import fs from 'fs';
import path from 'path';

export default function handler(req, res) {
  try {
    // Absolute path to zip file
    const filePath = path.join(process.cwd(), 'files', 'agent-installer.zip');

    // Check if file exists
    if (!fs.existsSync(filePath)) {
      return res.status(404).send('File not found');
    }

    // Set headers for download
    res.setHeader('Content-Disposition', 'attachment; filename=agent-installer.zip');
    res.setHeader('Content-Type', 'application/zip');

    // Stream file
    const fileStream = fs.createReadStream(filePath);
    fileStream.pipe(res);

  } catch (error) {
    console.error(error);
    res.status(500).send('Server error');
  }
}
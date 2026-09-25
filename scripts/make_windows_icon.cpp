// SPDX-License-Identifier: GPL-3.0-or-later
// Render the repository's vector mark at each native Windows icon size.
#include <QGuiApplication>
#include <QSvgRenderer>
#include <QPainter>
#include <QFile>
#include <QBuffer>
#include <QDataStream>
#include <QVector>

int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);
    if(argc!=3) return 2;
    QSvgRenderer svg(QString::fromLocal8Bit(argv[1]));
    if(!svg.isValid()) return 3;
    const QList<int> sizes{16,24,32,48,64,128,256};
    QVector<QByteArray> images;
    for(int size:sizes) {
        QImage image(size,size,QImage::Format_ARGB32);
        image.fill(Qt::transparent);
        QPainter painter(&image);
        painter.setRenderHint(QPainter::Antialiasing);
        svg.render(&painter); painter.end();
        QByteArray bytes; QBuffer buffer(&bytes); buffer.open(QIODevice::WriteOnly);
        if(!image.save(&buffer,"PNG")) return 4;
        images.push_back(bytes);
    }
    QFile file(QString::fromLocal8Bit(argv[2]));
    if(!file.open(QIODevice::WriteOnly)) return 5;
    QDataStream out(&file); out.setByteOrder(QDataStream::LittleEndian);
    out << quint16(0) << quint16(1) << quint16(sizes.size());
    quint32 offset=6+16*sizes.size();
    for(int i=0;i<sizes.size();++i) {
        out << quint8(sizes[i]%256) << quint8(sizes[i]%256) << quint8(0) << quint8(0)
            << quint16(1) << quint16(32) << quint32(images[i].size()) << offset;
        offset+=images[i].size();
    }
    for(const auto& bytes:images) out.writeRawData(bytes.data(),bytes.size());
    return out.status()==QDataStream::Ok ? 0 : 6;
}
